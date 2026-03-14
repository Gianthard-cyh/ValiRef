#!/usr/bin/env python3
"""
Minimal arXiv metadata importer.
Imports arXiv metadata from local file to PostgreSQL.
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


def parse_metadata(filepath: str, limit: int = None):
    """Parse arXiv metadata JSON and yield paper records."""
    count = 0

    # Detect if gzipped
    open_func = gzip.open if filepath.endswith(".gz") else open

    with open_func(filepath, "rt", encoding="utf-8") as f:
        for line in f:
            if limit and count >= limit:
                break

            data = json.loads(line)

            # Extract fields (handle different schema)
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

            # Parse categories
            categories = data.get("categories", [])
            if isinstance(categories, str):
                categories = categories.split()

            # Parse year from various date fields
            year = None
            date = (
                data.get("date") or data.get("created") or data.get("update_date", "")
            )
            if date and len(date) >= 4:
                try:
                    year = int(date[:4])
                except ValueError:
                    pass

            doi = data.get("doi", "")
            journal = data.get("journal-ref", "")

            yield (paper_id, title, authors, abstract, categories, year, doi, journal)
            count += 1


def import_metadata(filepath: str, limit: int = None):
    """Import arXiv metadata to PostgreSQL."""
    print("🚀 Importing arXiv metadata")
    print(f"   File: {filepath}")

    # Connect to DB
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    try:
        # Check existing count
        cursor.execute("SELECT COUNT(*) FROM papers")
        existing = cursor.fetchone()[0]
        print(f"📊 Existing papers: {existing:,}")

        # Parse and import
        print("📥 Importing...")
        batch = []
        imported = 0

        for record in tqdm(
            parse_metadata(filepath, limit), desc="Importing", unit="papers"
        ):
            batch.append(record)

            if len(batch) >= 1000:
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

        print(f"\n✅ Imported: {imported:,} papers")

    finally:
        cursor.close()
        conn.close()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Import arXiv metadata")
    parser.add_argument("filepath", help="Path to arXiv metadata JSON file")
    parser.add_argument(
        "-l", "--limit", type=int, default=None, help="Max papers to import"
    )
    args = parser.parse_args()

    import_metadata(args.filepath, args.limit)


if __name__ == "__main__":
    main()
