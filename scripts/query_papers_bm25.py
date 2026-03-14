#!/usr/bin/env python3
"""
BM25 search using ParadeDB (pg_search).
Uses ParadeDB's native @@@ operator and paradedb.score().
Supports filtering by source (arxiv/dblp) and year.
"""

import os
import psycopg2

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "user": os.getenv("DB_USER", "valiref"),
    "password": os.getenv("DB_PASSWORD", "valiref_secret"),
    "database": os.getenv("DB_NAME", "arxiv_db"),
}


def search_bm25(
    query: str,
    top_k: int = 10,
    year_from: int = None,
    year_to: int = None,
    source: str = None,
    venue: str = None,
):
    """
    Search papers using ParadeDB BM25.
    Uses @@@ operator for BM25 query.

    Args:
        query: Search query string
        top_k: Number of results to return
        year_from: Filter by minimum year
        year_to: Filter by maximum year
        source: Filter by source ('arxiv', 'dblp', or None for all)
        venue: Filter by venue (partial match)
    """
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    try:
        # Build WHERE clause
        where_clauses = ["(title || ' ' || COALESCE(abstract, '')) @@@ %s"]
        params = [query]

        if year_from:
            where_clauses.append("year >= %s")
            params.append(year_from)

        if year_to:
            where_clauses.append("year <= %s")
            params.append(year_to)

        if source:
            where_clauses.append("source = %s")
            params.append(source)

        if venue:
            where_clauses.append("venue ILIKE %s")
            params.append(f"%{venue}%")

        sql = f"""
            SELECT
                id,
                title,
                authors,
                year,
                venue,
                source,
                paradedb.score(id) as rank
            FROM papers
            WHERE {" AND ".join(where_clauses)}
            ORDER BY rank DESC
            LIMIT %s
        """
        params.append(top_k)

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        # Build filter description
        filters = []
        if year_from:
            filters.append(f"year >= {year_from}")
        if year_to:
            filters.append(f"year <= {year_to}")
        if source:
            filters.append(f"source = {source}")
        if venue:
            filters.append(f"venue ~ {venue}")

        filter_str = f" ({', '.join(filters)})" if filters else ""

        print(f"\n{'=' * 70}")
        print(f'ParadeDB BM25 Search: "{query}"{filter_str}')
        print(f"{'=' * 70}\n")

        if not rows:
            print("No results found.")
            return

        for i, row in enumerate(rows, 1):
            paper_id = row[0]
            title = row[1]
            authors = row[2] or []
            year = row[3]
            paper_venue = row[4]
            paper_source = row[5]
            rank = row[6]

            source_tag = f"[{paper_source.upper()}]"
            venue_str = f" @ {paper_venue}" if paper_venue else ""

            print(f"{i}. {source_tag} [{paper_id}] rank={rank:.4f}")
            print(f"   Title: {title[:80]}{'...' if len(title) > 80 else ''}")
            author_list = authors[:3] if authors else []
            print(
                f"   Authors: {', '.join(author_list)}{' et al.' if len(authors) > 3 else ''}"
            )
            print(f"   Year: {year}{venue_str}\n")

        # Show total counts by source
        cursor.execute("""
            SELECT source, COUNT(*) FROM papers
            WHERE source IN ('arxiv', 'dblp')
            GROUP BY source
        """)
        counts = cursor.fetchall()
        print("-" * 70)
        print("Database stats:")
        for src, cnt in counts:
            print(f"   {src}: {cnt:,} papers")

    finally:
        cursor.close()
        conn.close()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="ParadeDB BM25 search")
    parser.add_argument("query", help="Search query")
    parser.add_argument("-k", "--top-k", type=int, default=10, help="Number of results")
    parser.add_argument(
        "-y", "--year-from", type=int, default=None, help="Filter by minimum year"
    )
    parser.add_argument(
        "-Y", "--year-to", type=int, default=None, help="Filter by maximum year"
    )
    parser.add_argument(
        "-s",
        "--source",
        type=str,
        default=None,
        choices=["arxiv", "dblp"],
        help="Filter by source (arxiv or dblp)",
    )
    parser.add_argument(
        "-v", "--venue", type=str, default=None, help="Filter by venue (partial match)"
    )
    args = parser.parse_args()

    search_bm25(
        args.query, args.top_k, args.year_from, args.year_to, args.source, args.venue
    )


if __name__ == "__main__":
    main()
