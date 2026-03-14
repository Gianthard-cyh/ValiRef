#!/usr/bin/env python3
"""
DBLP XML importer for ValiRef.
Imports DBLP papers from XML dump to PostgreSQL/ParadeDB.

DBLP XML format:
- Root: <dblp>
- Entry types: article, inproceedings, book, phdthesis, incollection
- Fields: key, title, author[], year, booktitle/journal, ee (DOI), url

Usage:
    python import_dblp.py /path/to/dblp.xml.gz
    python import_dblp.py /path/to/dblp.xml
"""

import os
import re
import gzip
import html
import time
from datetime import datetime
import psycopg2
from psycopg2.extras import execute_values

# Try to import lxml, fall back to xml.etree
try:
    from lxml import etree

    HAS_LXML = True
except ImportError:
    import xml.etree.ElementTree as etree

    HAS_LXML = False
    print(
        "⚠️  lxml not found, using xml.etree (slower). Install lxml for better performance."
    )

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "user": os.getenv("DB_USER", "valiref"),
    "password": os.getenv("DB_PASSWORD", "valiref_secret"),
    "database": os.getenv("DB_NAME", "arxiv_db"),
}

BATCH_SIZE = 2000
REPORT_INTERVAL = 100000

# Entry types we want to import
VALID_ENTRY_TYPES = {"article", "inproceedings", "book", "phdthesis", "incollection"}

# HTML entities that may appear in DBLP
HTML_ENTITIES = {
    "&uuml;",
    "&ouml;",
    "&auml;",
    "&szlig;",  # German
    "&eacute;",
    "&egrave;",
    "&agrave;",
    "&ccedil;",  # French
    "&ntilde;",
    "&iacute;",
    "&oacute;",  # Spanish
    "&aring;",
    "&oslash;",
    "&aelig;",  # Scandinavian
}


def decode_html_entities(text: str) -> str:
    """Decode HTML entities like &uuml; &amp; etc."""
    if not text:
        return ""
    return html.unescape(text)


def clean_text(text: str) -> str:
    """Clean text: remove newlines, decode HTML entities."""
    if not text:
        return ""
    text = text.replace("\n", " ").replace("\r", " ")
    text = decode_html_entities(text)
    return text.strip()


class EntityUnescapeStream:
    """Stream wrapper that unescapes HTML entities line by line."""

    def __init__(self, stream):
        self.stream = stream
        self.buffer = b""
        self.entity_pattern = re.compile(r"&([a-zA-Z][a-zA-Z0-9]*);")

    def read(self, size=-1):
        data = self.stream.read(size)
        if isinstance(data, bytes):
            text = data.decode("utf-8", errors="replace")
        else:
            text = data
        # Replace undefined HTML entities with their Unicode equivalents
        return html.unescape(text).encode("utf-8")

    def __iter__(self):
        for line in self.stream:
            if isinstance(line, bytes):
                line = line.decode("utf-8", errors="replace")
            yield html.unescape(line).encode("utf-8")

    def close(self):
        self.stream.close()


def parse_dblp_xml(filepath: str):
    """
    Parse DBLP XML and yield paper records.
    Uses iterative parsing to handle large files.
    Pre-processes to handle HTML entities.
    """
    count = 0
    skipped = 0

    print("   Preparing XML parser with HTML entity handling...")

    # Create a recovery parser
    # Note: lxml.iterparse doesn't support parser argument, so we skip it

    # Detect if gzipped and open with entity unescaping
    if filepath.endswith(".gz"):
        raw = gzip.open(filepath, "rb")
    else:
        raw = open(filepath, "rb")

    # Wrap with entity unescaper
    stream = EntityUnescapeStream(raw)

    context = etree.iterparse(stream, events=("end",), tag=VALID_ENTRY_TYPES)

    try:
        for event, elem in context:
            try:
                paper = parse_entry(elem)
                if paper:
                    yield paper
                    count += 1

                    if count % REPORT_INTERVAL == 0:
                        print(f"   Parsed {count:,} entries...")
                else:
                    skipped += 1

            except Exception as e:
                skipped += 1
                if skipped % 10000 == 0:
                    print(
                        f"   Warning: Skipped {skipped} entries so far (last error: {e})"
                    )

            finally:
                # Clear element to free memory
                elem.clear()
                # Also eliminate now-empty references from the root node
                while elem.getprevious() is not None:
                    del elem.getparent()[0]

    finally:
        stream.close()

    print(f"   Parsing complete: {count:,} valid, {skipped:,} skipped")


def parse_entry(elem) -> tuple:
    """Parse a single DBLP entry element into a paper record."""
    # Entry type and key
    entry_type = elem.tag
    dblp_key = elem.get("key", "")

    if not dblp_key:
        return None

    # Build ID from DBLP key
    paper_id = f"dblp:{dblp_key}"

    # Extract title
    title_elem = elem.find("title")
    title = clean_text(title_elem.text if title_elem is not None else "")

    if not title:
        # Try to get title from crossref or other fields
        title = f"[{entry_type}] {dblp_key}"

    # Extract authors
    authors = []
    for author in elem.findall("author"):
        if author.text:
            authors.append(clean_text(author.text))

    # Extract year
    year = None
    year_elem = elem.find("year")
    if year_elem is not None and year_elem.text:
        try:
            year = int(year_elem.text)
        except ValueError:
            pass

    # Extract venue (booktitle for inproceedings/incollection, journal for article)
    venue = None
    if entry_type in ("inproceedings", "incollection"):
        booktitle = elem.find("booktitle")
        if booktitle is not None and booktitle.text:
            venue = clean_text(booktitle.text)
    elif entry_type == "article":
        journal = elem.find("journal")
        if journal is not None and journal.text:
            venue = clean_text(journal.text)
    elif entry_type == "book":
        publisher = elem.find("publisher")
        if publisher is not None and publisher.text:
            venue = clean_text(publisher.text)
    elif entry_type == "phdthesis":
        school = elem.find("school")
        if school is not None and school.text:
            venue = clean_text(school.text)

    # Extract DOI from ee element
    doi = ""
    for ee in elem.findall("ee"):
        if ee.text:
            ee_text = ee.text.strip()
            if "doi.org" in ee_text:
                # Extract DOI from URL
                doi = ee_text.split("doi.org/")[-1]
                break
            elif ee_text.startswith("10."):
                doi = ee_text
                break

    # DBLP has no abstract, categories, or embedding
    abstract = None
    categories = []
    journal_ref = None
    source = "dblp"

    return (
        paper_id,
        title,
        authors,
        abstract,
        categories,
        year,
        doi,
        journal_ref,
        venue,
        source,
    )


def import_dblp(filepath: str, limit: int = None):
    """Import DBLP papers to PostgreSQL."""
    print("🚀 Importing DBLP papers")
    print(f"   File: {filepath}")
    print(f"   Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Connect to DB
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    try:
        # Check current counts
        cursor.execute("SELECT COUNT(*) FROM papers")
        total_existing = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM papers WHERE source = 'dblp'")
        dblp_existing = cursor.fetchone()[0]

        print("\n📊 Current database state:")
        print(f"   Total papers: {total_existing:,}")
        print(f"   Existing DBLP papers: {dblp_existing:,}")

        # Parse and import
        print(f"\n📥 Parsing and importing... (batch size: {BATCH_SIZE})")

        batch = []
        imported = dblp_existing  # Start from existing count
        errors = 0
        start_time = time.time()

        for record in parse_dblp_xml(filepath):
            if limit and imported >= limit:
                break

            batch.append(record)

            if len(batch) >= BATCH_SIZE:
                try:
                    execute_values(
                        cursor,
                        """
                        INSERT INTO papers (
                            id, title, authors, abstract, categories,
                            year, doi, journal_ref, venue, source
                        )
                        VALUES %s
                        ON CONFLICT (id) DO UPDATE SET
                            title = EXCLUDED.title,
                            authors = EXCLUDED.authors,
                            year = EXCLUDED.year,
                            doi = EXCLUDED.doi,
                            venue = EXCLUDED.venue
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

                # Progress report
                if (imported - dblp_existing) % REPORT_INTERVAL == 0:
                    elapsed = time.time() - start_time
                    speed = (imported - dblp_existing) / elapsed if elapsed > 0 else 0
                    print(
                        f"\n📈 Progress: {imported:,} imported | {speed:.0f} papers/sec"
                    )

        # Final batch
        if batch:
            try:
                execute_values(
                    cursor,
                    """
                    INSERT INTO papers (
                        id, title, authors, abstract, categories,
                        year, doi, journal_ref, venue, source
                    )
                    VALUES %s
                    ON CONFLICT (id) DO UPDATE SET
                        title = EXCLUDED.title,
                        authors = EXCLUDED.authors,
                        year = EXCLUDED.year,
                        doi = EXCLUDED.doi,
                        venue = EXCLUDED.venue
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
        newly_imported = imported - dblp_existing

        print(f"\n{'=' * 60}")
        print("✅ Import Complete!")
        print(f"{'=' * 60}")
        print(f"   Newly imported: {newly_imported:,} papers")
        print(f"   Errors: {errors:,}")
        if elapsed > 0:
            print(f"   Time: {elapsed / 60:.1f} minutes")
            print(f"   Speed: {newly_imported / elapsed:.0f} papers/sec")

        # Statistics
        cursor.execute("SELECT COUNT(*) FROM papers")
        total_in_db = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM papers WHERE source = 'dblp'")
        dblp_in_db = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM papers WHERE source = 'arxiv'")
        arxiv_in_db = cursor.fetchone()[0]

        print("\n📊 Database stats:")
        print(f"   Total papers: {total_in_db:,}")
        print(f"   arXiv papers: {arxiv_in_db:,}")
        print(f"   DBLP papers: {dblp_in_db:,}")

        cursor.execute(
            "SELECT MIN(year), MAX(year) FROM papers WHERE source = 'dblp' AND year IS NOT NULL"
        )
        year_range = cursor.fetchone()
        if year_range and year_range[0]:
            print(f"   DBLP year range: {year_range[0]} - {year_range[1]}")

        # Rebuild BM25 index
        print("\n🔧 Rebuilding BM25 index...")
        cursor.execute("DROP INDEX IF EXISTS idx_papers_bm25")
        cursor.execute("""
            CREATE INDEX idx_papers_bm25 ON papers
            USING bm25(id, title, abstract)
            WITH (key_field='id')
        """)
        conn.commit()
        print("   ✓ BM25 index rebuilt")

        print(f"\n⏱️  Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    finally:
        cursor.close()
        conn.close()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Import DBLP papers from XML")
    parser.add_argument("filepath", help="Path to DBLP XML file (.xml or .xml.gz)")
    parser.add_argument(
        "-l", "--limit", type=int, default=None, help="Max papers to import"
    )
    args = parser.parse_args()

    import_dblp(args.filepath, args.limit)


if __name__ == "__main__":
    main()
