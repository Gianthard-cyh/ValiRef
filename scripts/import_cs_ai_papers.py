#!/usr/bin/env python3
"""
Import recent CS/AI papers for testing BM25 search.
Filters by category and year.
"""

import os
import json
import gzip
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

# CS/AI related categories
AI_CATEGORIES = {
    "cs.AI",  # Artificial Intelligence
    "cs.CL",  # Computation and Language (NLP)
    "cs.LG",  # Machine Learning
    "cs.CV",  # Computer Vision
    "cs.IR",  # Information Retrieval
    "cs.NE",  # Neural and Evolutionary Computing
    "cs.RO",  # Robotics
    "cs.HC",  # Human-Computer Interaction
    "cs.SD",  # Sound
    "cs.MM",  # Multimedia
    "cs.DB",  # Databases (for LLM apps)
}


def parse_cs_ai_papers(filepath: str, year_from: int = 2020, limit: int = None):
    """Parse arXiv metadata and filter for recent CS/AI papers."""
    count = 0
    skipped = 0
    matched = 0

    # Detect if gzipped
    open_func = gzip.open if filepath.endswith(".gz") else open

    print(f"🔍 Scanning for CS/AI papers (year >= {year_from})...")

    with open_func(filepath, "rt", encoding="utf-8") as f:
        for line in tqdm(f, desc="Scanning", unit="papers", mininterval=1):
            if limit and matched >= limit:
                break

            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Parse year
            year = None
            date = data.get("update_date") or data.get("created", "")
            if date and len(date) >= 4:
                try:
                    year = int(date[:4])
                except ValueError:
                    continue

            # Filter by year
            if year is None or year < year_from:
                skipped += 1
                continue

            # Parse categories
            categories = data.get("categories", "")
            if isinstance(categories, str):
                cat_list = categories.split()
            else:
                cat_list = categories

            # Filter by CS/AI categories
            has_ai_cat = any(cat in AI_CATEGORIES for cat in cat_list)
            if not has_ai_cat:
                skipped += 1
                continue

            # Extract fields
            paper_id = data.get("id", "")
            title = data.get("title", "").replace("\n", " ").strip()
            abstract = data.get("abstract", "").replace("\n", " ").strip()

            # Parse authors - can be string (comma-separated) or list
            authors_raw = data.get("authors", "")
            if isinstance(authors_raw, str):
                # Split by comma and clean up
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

            doi = data.get("doi", "")
            journal = data.get("journal-ref", "")

            yield (paper_id, title, authors, abstract, cat_list, year, doi, journal)
            matched += 1
            count += 1

    print(f"✅ Found {matched} CS/AI papers (skipped {skipped})")


def import_cs_ai_papers(filepath: str, year_from: int = 2020, limit: int = None):
    """Import recent CS/AI papers to PostgreSQL."""
    print("🚀 Importing recent CS/AI papers")
    print(f"   Source: {filepath}")
    print(f"   Year: >= {year_from}")
    print(f"   Categories: {', '.join(sorted(AI_CATEGORIES)[:5])}...")

    # Connect to DB
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    try:
        # Check existing count
        cursor.execute("SELECT COUNT(*) FROM papers WHERE year >= %s", (year_from,))
        existing = cursor.fetchone()[0]
        print(f"📊 Existing recent papers: {existing:,}")

        # Parse and import
        batch = []
        imported = 0

        for record in parse_cs_ai_papers(filepath, year_from, limit):
            batch.append(record)

            if len(batch) >= 500:
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
                batch = []

        # Final batch
        if batch:
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

        print(f"\n✅ Imported: {imported:,} CS/AI papers")

        # Show summary by year
        cursor.execute(
            """
            SELECT year, COUNT(*) FROM papers
            WHERE year >= %s
            GROUP BY year ORDER BY year DESC
        """,
            (year_from,),
        )
        print("\n📊 Papers by year:")
        for row in cursor.fetchall():
            print(f"   {row[0]}: {row[1]:,}")

        # Show top categories
        cursor.execute(
            """
            SELECT UNNEST(categories) as cat, COUNT(*) FROM papers
            WHERE year >= %s
            GROUP BY cat ORDER BY COUNT(*) DESC LIMIT 10
        """,
            (year_from,),
        )
        print("\n📊 Top categories:")
        for row in cursor.fetchall():
            if row[0].startswith("cs."):
                print(f"   {row[0]}: {row[1]:,}")

    finally:
        cursor.close()
        conn.close()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Import recent CS/AI papers")
    parser.add_argument("filepath", help="Path to arXiv metadata JSON file")
    parser.add_argument(
        "-y",
        "--year-from",
        type=int,
        default=2020,
        help="Import papers from this year onwards (default: 2020)",
    )
    parser.add_argument(
        "-l", "--limit", type=int, default=None, help="Max papers to import"
    )
    args = parser.parse_args()

    import_cs_ai_papers(args.filepath, args.year_from, args.limit)


if __name__ == "__main__":
    main()
