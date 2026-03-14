#!/usr/bin/env python3
"""
Data validation and reporting script.
Validates data integrity after DBLP import and generates statistics report.

Usage:
    python validate_and_report.py
    python validate_and_report.py --validate-only
    python validate_and_report.py --report-only --output report.json
"""

import os
import json
import psycopg2
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "user": os.getenv("DB_USER", "valiref"),
    "password": os.getenv("DB_PASSWORD", "valiref_secret"),
    "database": os.getenv("DB_NAME", "arxiv_db"),
}


@dataclass
class ValidationReport:
    """Complete validation and statistics report."""

    timestamp: str
    total_papers: int
    arxiv_count: int
    dblp_count: int
    arxiv_percentage: float
    dblp_percentage: float

    # arXiv stats
    arxiv_year_range: Tuple[int, int]
    arxiv_with_abstract: int
    arxiv_with_embedding: int
    arxiv_categories: List[Tuple[str, int]]

    # DBLP stats
    dblp_year_range: Tuple[int, int]
    dblp_with_venue: int
    dblp_top_venues: List[Tuple[str, int]]

    # Index status
    indexes: Dict[str, bool]
    table_size: str

    # Validation results
    validation_passed: bool
    validation_errors: List[str]


def get_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)


def validate_database(conn) -> Tuple[bool, List[str]]:
    """Run validation checks on the database."""
    errors = []
    cursor = conn.cursor()

    try:
        # 1. Check if source column exists
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'papers' AND column_name = 'source'
        """)
        if not cursor.fetchone():
            errors.append("source column does not exist")

        # 2. Check if venue column exists
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'papers' AND column_name = 'venue'
        """)
        if not cursor.fetchone():
            errors.append("venue column does not exist")

        # 3. Check for NULL sources
        cursor.execute("SELECT COUNT(*) FROM papers WHERE source IS NULL")
        null_count = cursor.fetchone()[0]
        if null_count > 0:
            errors.append(f"{null_count:,} papers have NULL source")

        # 4. Check for invalid sources
        cursor.execute("""
            SELECT DISTINCT source FROM papers
            WHERE source NOT IN ('arxiv', 'dblp') AND source IS NOT NULL
        """)
        invalid_sources = cursor.fetchall()
        if invalid_sources:
            errors.append(f"Invalid sources found: {[s[0] for s in invalid_sources]}")

        # 5. Check BM25 index exists
        cursor.execute("""
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'papers' AND indexname = 'idx_papers_bm25'
        """)
        if not cursor.fetchone():
            errors.append("BM25 index (idx_papers_bm25) does not exist")

        # 6. Check source index exists
        cursor.execute("""
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'papers' AND indexname = 'idx_papers_source'
        """)
        if not cursor.fetchone():
            errors.append("Source index (idx_papers_source) does not exist")

        # 7. Verify expected data volume
        cursor.execute("SELECT COUNT(*) FROM papers")
        total = cursor.fetchone()[0]
        if total < 5000000:  # Expect ~6.8M (2.97M arXiv + ~3.9M DBLP)
            errors.append(f"Total papers ({total:,}) below expected minimum (5M)")

        # 8. Check arXiv has embeddings
        cursor.execute("""
            SELECT COUNT(*) FROM papers
            WHERE source = 'arxiv' AND embedding IS NULL
        """)
        arxiv_no_emb = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM papers WHERE source = 'arxiv'")
        arxiv_total = cursor.fetchone()[0]
        if arxiv_total > 0 and arxiv_no_emb == arxiv_total:
            errors.append("No arXiv papers have embeddings")

        # 9. Check DBLP has no embeddings (expected)
        cursor.execute("""
            SELECT COUNT(*) FROM papers
            WHERE source = 'dblp' AND embedding IS NOT NULL
        """)
        dblp_with_emb = cursor.fetchone()[0]
        if dblp_with_emb > 0:
            errors.append(f"{dblp_with_emb:,} DBLP papers unexpectedly have embeddings")

    finally:
        cursor.close()

    return len(errors) == 0, errors


def generate_report(conn) -> ValidationReport:
    """Generate comprehensive statistics report."""
    cursor = conn.cursor()

    try:
        # Basic counts
        cursor.execute("SELECT COUNT(*) FROM papers")
        total_papers = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM papers WHERE source = 'arxiv'")
        arxiv_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM papers WHERE source = 'dblp'")
        dblp_count = cursor.fetchone()[0]

        arxiv_pct = (arxiv_count / total_papers * 100) if total_papers > 0 else 0
        dblp_pct = (dblp_count / total_papers * 100) if total_papers > 0 else 0

        # arXiv stats
        cursor.execute("""
            SELECT MIN(year), MAX(year)
            FROM papers WHERE source = 'arxiv' AND year IS NOT NULL
        """)
        arxiv_year_range = cursor.fetchone()

        cursor.execute("""
            SELECT COUNT(*) FROM papers
            WHERE source = 'arxiv' AND abstract IS NOT NULL AND abstract != ''
        """)
        arxiv_with_abstract = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM papers
            WHERE source = 'arxiv' AND embedding IS NOT NULL
        """)
        arxiv_with_embedding = cursor.fetchone()[0]

        # Top arXiv categories
        cursor.execute("""
            SELECT cat, COUNT(*) FROM (
                SELECT UNNEST(categories) as cat FROM papers WHERE source = 'arxiv'
            ) t
            GROUP BY cat ORDER BY COUNT(*) DESC LIMIT 10
        """)
        arxiv_categories = cursor.fetchall()

        # DBLP stats
        cursor.execute("""
            SELECT MIN(year), MAX(year)
            FROM papers WHERE source = 'dblp' AND year IS NOT NULL
        """)
        dblp_year_range = cursor.fetchone()

        cursor.execute("""
            SELECT COUNT(*) FROM papers
            WHERE source = 'dblp' AND venue IS NOT NULL AND venue != ''
        """)
        dblp_with_venue = cursor.fetchone()[0]

        # Top DBLP venues
        cursor.execute("""
            SELECT venue, COUNT(*) FROM papers
            WHERE source = 'dblp' AND venue IS NOT NULL
            GROUP BY venue ORDER BY COUNT(*) DESC LIMIT 10
        """)
        dblp_top_venues = cursor.fetchall()

        # Table size
        cursor.execute("""
            SELECT pg_size_pretty(pg_total_relation_size('papers'))
        """)
        table_size = cursor.fetchone()[0]

        # Index status
        cursor.execute("""
            SELECT indexname FROM pg_indexes WHERE tablename = 'papers'
        """)
        existing_indexes = {row[0] for row in cursor.fetchall()}
        indexes = {
            "idx_papers_bm25": "idx_papers_bm25" in existing_indexes,
            "idx_papers_source": "idx_papers_source" in existing_indexes,
            "idx_papers_year": "idx_papers_year" in existing_indexes,
            "idx_papers_categories": "idx_papers_categories" in existing_indexes,
        }

    finally:
        cursor.close()

    # Run validation
    validation_passed, validation_errors = validate_database(conn)

    return ValidationReport(
        timestamp=datetime.now().isoformat(),
        total_papers=total_papers,
        arxiv_count=arxiv_count,
        dblp_count=dblp_count,
        arxiv_percentage=arxiv_pct,
        dblp_percentage=dblp_pct,
        arxiv_year_range=arxiv_year_range or (None, None),
        arxiv_with_abstract=arxiv_with_abstract,
        arxiv_with_embedding=arxiv_with_embedding,
        arxiv_categories=arxiv_categories,
        dblp_year_range=dblp_year_range or (None, None),
        dblp_with_venue=dblp_with_venue,
        dblp_top_venues=dblp_top_venues,
        indexes=indexes,
        table_size=table_size,
        validation_passed=validation_passed,
        validation_errors=validation_errors,
    )


def print_report(report: ValidationReport):
    """Print formatted report."""
    print("\n" + "=" * 70)
    print("VALIDATION & STATISTICS REPORT")
    print("=" * 70)
    print(f"Generated: {report.timestamp}")
    print()

    # Validation status
    print("VALIDATION STATUS:")
    print("-" * 70)
    if report.validation_passed:
        print("   PASSED - All checks passed!")
    else:
        print("   FAILED - Issues found:")
        for error in report.validation_errors:
            print(f"      - {error}")
    print()

    # Data distribution
    print("DATA DISTRIBUTION:")
    print("-" * 70)
    print(f"   Total papers:        {report.total_papers:,}")
    print(
        f"   arXiv papers:        {report.arxiv_count:,} ({report.arxiv_percentage:.1f}%)"
    )
    print(
        f"   DBLP papers:         {report.dblp_count:,} ({report.dblp_percentage:.1f}%)"
    )
    print(f"   Table size:          {report.table_size}")
    print()

    # arXiv details
    print("ARXIV STATISTICS:")
    print("-" * 70)
    print(
        f"   Year range:          {report.arxiv_year_range[0]} - {report.arxiv_year_range[1]}"
    )
    print(f"   With abstract:       {report.arxiv_with_abstract:,}")
    print(f"   With embedding:      {report.arxiv_with_embedding:,}")
    print("   Top categories:")
    for cat, count in report.arxiv_categories[:5]:
        print(f"      {cat}: {count:,}")
    print()

    # DBLP details
    print("DBLP STATISTICS:")
    print("-" * 70)
    print(
        f"   Year range:          {report.dblp_year_range[0]} - {report.dblp_year_range[1]}"
    )
    print(f"   With venue:          {report.dblp_with_venue:,}")
    print("   Top venues:")
    for venue, count in report.dblp_top_venues[:5]:
        display_venue = venue[:40] + "..." if len(venue) > 40 else venue
        print(f"      {display_venue}: {count:,}")
    print()

    # Index status
    print("INDEX STATUS:")
    print("-" * 70)
    for idx_name, exists in report.indexes.items():
        status = "OK" if exists else "MISSING"
        print(f"   {idx_name}: {status}")
    print()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Validate and report on database")
    parser.add_argument(
        "--validate-only", action="store_true", help="Only run validation checks"
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Only generate report (skip validation)",
    )
    parser.add_argument(
        "-o", "--output", type=str, default=None, help="Save report to JSON file"
    )
    args = parser.parse_args()

    print("🚀 Database Validation & Reporting")
    print(f"   Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    conn = get_connection()

    try:
        if args.validate_only:
            print("\n📋 Running validation checks...")
            passed, errors = validate_database(conn)
            if passed:
                print("✅ All validation checks passed!")
            else:
                print("❌ Validation failed:")
                for error in errors:
                    print(f"   - {error}")
            return

        # Generate full report
        report = generate_report(conn)
        print_report(report)

        # Save to file if requested
        if args.output:
            report_dict = asdict(report)
            # Convert tuples to lists for JSON serialization
            report_dict["arxiv_year_range"] = list(report.arxiv_year_range)
            report_dict["dblp_year_range"] = list(report.dblp_year_range)
            report_dict["arxiv_categories"] = [list(c) for c in report.arxiv_categories]
            report_dict["dblp_top_venues"] = [list(v) for v in report.dblp_top_venues]

            with open(args.output, "w") as f:
                json.dump(report_dict, f, indent=2)
            print(f"💾 Report saved to: {args.output}")

        # Exit with error code if validation failed
        if not report.validation_passed:
            exit(1)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
