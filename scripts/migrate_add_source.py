#!/usr/bin/env python3
"""
Migration script: Add source field to existing arXiv papers.
Updates existing papers to have source='arxiv'.
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


def migrate_add_source():
    """Add source column and update existing data."""
    print("🚀 Starting migration: Add source field")

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    try:
        # 1. Check if source column exists
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'papers' AND column_name = 'source'
        """)
        if cursor.fetchone():
            print("   ✓ source column already exists")
        else:
            print("   Adding source column...")
            cursor.execute(
                "ALTER TABLE papers ADD COLUMN source VARCHAR(20) DEFAULT 'arxiv'"
            )
            conn.commit()
            print("   ✓ source column added")

        # 2. Check if venue column exists
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'papers' AND column_name = 'venue'
        """)
        if cursor.fetchone():
            print("   ✓ venue column already exists")
        else:
            print("   Adding venue column...")
            cursor.execute("ALTER TABLE papers ADD COLUMN venue VARCHAR(500)")
            conn.commit()
            print("   ✓ venue column added")

        # 3. Update existing papers with NULL source to 'arxiv'
        print("\n📊 Updating existing papers...")
        cursor.execute("SELECT COUNT(*) FROM papers WHERE source IS NULL")
        null_count = cursor.fetchone()[0]

        if null_count > 0:
            print(f"   Found {null_count:,} papers without source")
            cursor.execute("UPDATE papers SET source = 'arxiv' WHERE source IS NULL")
            conn.commit()
            print(f"   ✓ Updated {null_count:,} papers to source='arxiv'")
        else:
            print("   ✓ All papers already have source set")

        # 4. Create index on source if not exists
        cursor.execute("""
            SELECT indexname FROM pg_indexes
            WHERE tablename = 'papers' AND indexname = 'idx_papers_source'
        """)
        if cursor.fetchone():
            print("   ✓ idx_papers_source already exists")
        else:
            print("   Creating index on source column...")
            cursor.execute("CREATE INDEX idx_papers_source ON papers(source)")
            conn.commit()
            print("   ✓ Index created")

        # 5. Verify data
        cursor.execute("SELECT source, COUNT(*) FROM papers GROUP BY source")
        stats = cursor.fetchall()
        print("\n📊 Data distribution:")
        for source, count in stats:
            print(f"   {source or 'NULL'}: {count:,} papers")

        # 6. Rebuild BM25 index to include all papers
        print("\n🔧 Rebuilding BM25 index...")
        cursor.execute("DROP INDEX IF EXISTS idx_papers_bm25")
        cursor.execute("""
            CREATE INDEX idx_papers_bm25 ON papers
            USING bm25(id, title, abstract)
            WITH (key_field='id')
        """)
        conn.commit()
        print("   ✓ BM25 index rebuilt")

        # 7. Get total count
        cursor.execute("SELECT COUNT(*) FROM papers")
        total = cursor.fetchone()[0]
        print("\n✅ Migration complete!")
        print(f"   Total papers in database: {total:,}")

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    migrate_add_source()
