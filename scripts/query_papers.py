#!/usr/bin/env python3
"""
Paper similarity search using pgvector.
Note: Only arXiv papers have embeddings (DBLP papers have NULL embeddings).
"""

import os
import psycopg2
from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "user": os.getenv("DB_USER", "valiref"),
    "password": os.getenv("DB_PASSWORD", "valiref_secret"),
    "database": os.getenv("DB_NAME", "arxiv_db"),
}


def search_similar(
    query: str, top_k: int = 10, source: str = None, year_from: int = None
):
    """
    Search for similar papers using cosine similarity.

    Note: Only arXiv papers have embeddings. DBLP papers will not appear
    in vector search results unless embeddings are generated separately.

    Args:
        query: Search query string
        top_k: Number of results to return
        source: Filter by source ('arxiv', 'dblp')
        year_from: Filter by minimum year
    """
    print("📥 Loading model...")
    model = SentenceTransformer(MODEL_NAME, device="cpu")

    print(f"🔍 Query: {query}")
    if source:
        print(f"   Source filter: {source}")
    if year_from:
        print(f"   Year filter: >= {year_from}")

    query_vec = model.encode(query, convert_to_numpy=True).tolist()

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    try:
        # Build WHERE clause
        where_clauses = ["embedding IS NOT NULL"]
        params = []

        if source:
            where_clauses.append("source = %s")
            params.append(source)
        else:
            # Default to arXiv for vector search (DBLP has no embeddings)
            where_clauses.append("source = 'arxiv'")

        if year_from:
            where_clauses.append("year >= %s")
            params.append(year_from)

        # Add query vector for the ORDER BY (twice for the two parameters)
        params.extend([query_vec, query_vec, top_k])

        sql = f"""
            SELECT id, title, authors, year, venue, source,
                   1 - (embedding <=> %s::vector) as similarity
            FROM papers
            WHERE {" AND ".join(where_clauses)}
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        print(f"\n{'=' * 70}")
        print("Vector Similarity Search Results:")
        print(f"{'=' * 70}\n")

        if not rows:
            print("No results found.")
            print("\nNote: Only arXiv papers have embeddings.")
            print("      DBLP papers need separate embedding generation.")
            return

        for i, row in enumerate(rows, 1):
            paper_id = row[0]
            title = row[1]
            authors = row[2] or []
            year = row[3]
            venue = row[4]
            paper_source = row[5]
            similarity = row[6]

            source_tag = f"[{paper_source.upper()}]"
            venue_str = f" @ {venue}" if venue else ""

            print(f"{i}. {source_tag} [{paper_id}] sim={similarity:.3f}")
            print(f"   Title: {title[:80]}{'...' if len(title) > 80 else ''}")
            author_list = authors[:3] if authors else []
            print(
                f"   Authors: {', '.join(author_list)}{' et al.' if len(authors) > 3 else ''}"
            )
            print(f"   Year: {year}{venue_str}\n")

        # Show database stats
        cursor.execute("""
            SELECT source, COUNT(*), COUNT(embedding)
            FROM papers
            WHERE source IN ('arxiv', 'dblp')
            GROUP BY source
        """)
        counts = cursor.fetchall()
        print("-" * 70)
        print("Database stats:")
        for src, total, with_emb in counts:
            print(f"   {src}: {total:,} papers ({with_emb:,} with embeddings)")

    finally:
        cursor.close()
        conn.close()


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Search similar papers using vector similarity"
    )
    parser.add_argument("query", help="Search query")
    parser.add_argument("-k", "--top-k", type=int, default=10, help="Number of results")
    parser.add_argument(
        "-s",
        "--source",
        type=str,
        default=None,
        choices=["arxiv", "dblp"],
        help="Filter by source (default: arxiv)",
    )
    parser.add_argument(
        "-y", "--year-from", type=int, default=None, help="Filter by minimum year"
    )
    args = parser.parse_args()

    search_similar(args.query, args.top_k, args.source, args.year_from)


if __name__ == "__main__":
    main()
