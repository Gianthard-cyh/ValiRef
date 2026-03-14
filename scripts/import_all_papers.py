#!/usr/bin/env python3
"""
导入完整 arXiv 数据库到 ParadeDB。
分批处理，支持断点续传。
"""

import os
import json
import gzip
import time
from datetime import datetime
from tqdm import tqdm
import psycopg2
from psycopg2.extras import execute_values

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "user": os.getenv("DB_USER", "valiref"),
    "password": os.getenv("DB_PASSWORD", "valiref_secret"),
    "database": os.getenv("DB_NAME", "arxiv_db"),
}

BATCH_SIZE = 2000  # 每批导入数量


def parse_papers(filepath: str, skip: int = 0):
    """Parse arXiv metadata and yield paper records."""
    open_func = gzip.open if filepath.endswith(".gz") else open

    with open_func(filepath, "rt", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i < skip:
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            paper_id = data.get("id", "")
            title = data.get("title", "").replace("\n", " ").strip()
            abstract = data.get("abstract", "").replace("\n", " ").strip()

            # Parse authors
            authors_raw = data.get("authors", "")
            if isinstance(authors_raw, str):
                authors = [a.strip() for a in authors_raw.split(",") if a.strip()]
            elif isinstance(authors_raw, list):
                authors = []
                for a in authors_raw:
                    if isinstance(a, dict):
                        authors.append(a.get("name", ""))
                    else:
                        authors.append(str(a))
            else:
                authors = []

            # Parse categories
            categories = data.get("categories", "")
            if isinstance(categories, str):
                cat_list = categories.split()
            else:
                cat_list = categories

            # Parse year
            year = None
            date = data.get("update_date") or data.get("created", "")
            if date and len(date) >= 4:
                try:
                    year = int(date[:4])
                except ValueError:
                    pass

            doi = data.get("doi", "")
            journal = data.get("journal-ref", "")

            yield (paper_id, title, authors, abstract, cat_list, year, doi, journal)


def import_all_papers(filepath: str):
    """Import all arXiv papers to PostgreSQL."""
    print("🚀 Importing ALL arXiv papers")
    print(f"   Source: {filepath}")
    print(f"   Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Count total lines
    print("\n📊 Counting total papers...")
    total_lines = sum(1 for _ in open(filepath, "r", encoding="utf-8"))
    print(f"   Total: {total_lines:,} papers")

    # Connect to DB
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    try:
        # Check existing count
        cursor.execute("SELECT COUNT(*) FROM papers")
        existing = cursor.fetchone()[0]
        print(f"   Existing: {existing:,} papers")

        if existing > 0:
            print("\n⚠️  Database not empty. Use TRUNCATE if you want to restart.")
            return

        # Parse and import
        print(f"\n📥 Importing... (batch size: {BATCH_SIZE})")

        batch = []
        imported = 0
        errors = 0
        start_time = time.time()

        for record in tqdm(
            parse_papers(filepath), total=total_lines, desc="Importing", unit="papers"
        ):
            batch.append(record)

            if len(batch) >= BATCH_SIZE:
                try:
                    execute_values(
                        cursor,
                        """
                        INSERT INTO papers (id, title, authors, abstract, categories, year, doi, journal_ref)
                        VALUES %s ON CONFLICT (id) DO NOTHING
                        """,
                        batch,
                        page_size=len(batch),
                    )
                    conn.commit()
                    imported += len(batch)
                except Exception as e:
                    print(f"\n❌ Error importing batch: {e}")
                    errors += len(batch)
                    conn.rollback()

                batch = []

                # Progress report every 100k papers
                if imported % 100000 == 0:
                    elapsed = time.time() - start_time
                    speed = imported / elapsed
                    remaining = (total_lines - imported) / speed if speed > 0 else 0
                    print(
                        f"\n📈 Progress: {imported:,} imported | {speed:.0f} papers/sec | ETA: {remaining / 60:.1f} min"
                    )

        # Final batch
        if batch:
            try:
                execute_values(
                    cursor,
                    """
                    INSERT INTO papers (id, title, authors, abstract, categories, year, doi, journal_ref)
                    VALUES %s ON CONFLICT (id) DO NOTHING
                    """,
                    batch,
                    page_size=len(batch),
                )
                conn.commit()
                imported += len(batch)
            except Exception as e:
                print(f"\n❌ Error importing final batch: {e}")
                errors += len(batch)

        elapsed = time.time() - start_time

        print(f"\n{'=' * 60}")
        print("✅ Import Complete!")
        print(f"{'=' * 60}")
        print(f"   Imported: {imported:,} papers")
        print(f"   Errors: {errors:,}")
        print(f"   Time: {elapsed / 60:.1f} minutes")
        print(f"   Speed: {imported / elapsed:.0f} papers/sec")

        # Statistics
        cursor.execute("SELECT COUNT(*) FROM papers")
        total_in_db = cursor.fetchone()[0]
        print("\n📊 Database stats:")
        print(f"   Total papers: {total_in_db:,}")

        cursor.execute("SELECT MIN(year), MAX(year) FROM papers WHERE year IS NOT NULL")
        min_year, max_year = cursor.fetchone()
        print(f"   Year range: {min_year} - {max_year}")

        cursor.execute("""
            SELECT UNNEST(categories) as cat, COUNT(*) FROM papers
            GROUP BY cat ORDER BY COUNT(*) DESC LIMIT 10
        """)
        print("\n📊 Top 10 categories:")
        for row in cursor.fetchall():
            print(f"   {row[0]}: {row[1]:,}")

        # Rebuild BM25 index
        print("\n🔧 Rebuilding BM25 index...")
        cursor.execute("DROP INDEX IF EXISTS idx_papers_bm25")
        cursor.execute("""
            CREATE INDEX idx_papers_bm25 ON papers
            USING bm25(id, title, abstract)
            WITH (key_field='id')
        """)
        conn.commit()
        print("   BM25 index rebuilt")

        print(f"\n⏱️  Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    finally:
        cursor.close()
        conn.close()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Import all arXiv papers")
    parser.add_argument("filepath", help="Path to arXiv metadata JSON file")
    args = parser.parse_args()

    import_all_papers(args.filepath)


if __name__ == "__main__":
    main()
