"""Local ParadeDB search tool implementation."""
import json
from typing import Optional

import asyncpg

from ...config import (
    DB_HOST,
    DB_NAME,
    DB_PASSWORD,
    DB_PORT,
    DB_USER,
)
from ...logger import logger
from ..base import SearchResult, SearchTool


class LocalDBSearch(SearchTool):
    """Local ParadeDB BM25 search for ValiRef Agent."""

    token_bucket_rate = 20.0  # Local database can support higher QPS

    def __init__(self):
        super().__init__()
        self.db_config = {
            "host": DB_HOST,
            "port": DB_PORT,
            "user": DB_USER,
            "password": DB_PASSWORD,
            "database": DB_NAME,
        }
        self._pool: Optional[asyncpg.Pool] = None

    async def _get_pool(self) -> asyncpg.Pool:
        """Get or create connection pool."""
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                host=self.db_config["host"],
                port=self.db_config["port"],
                user=self.db_config["user"],
                password=self.db_config["password"],
                database=self.db_config["database"],
                min_size=2,
                max_size=10,
            )
        return self._pool

    async def _perform_asearch(self, query: str, limit: int = 5) -> list[SearchResult]:
        """Search local ParadeDB using BM25."""
        pool = await self._get_pool()

        try:
            async with pool.acquire() as conn:
                # Escape the query for ParadeDB: wrap in double quotes to treat as phrase
                # This prevents special characters like ':' from being interpreted as field operators
                escaped_query = f'"{query.replace("\"", "\\\"")}"'

                # Use ParadeDB BM25 search with @@@ operator
                # Search in title and abstract fields
                # Note: Schema uses 'year' instead of 'published_date', 'journal_ref' for arxiv date
                sql = """
                    SELECT
                        id,
                        title,
                        authors,
                        year,
                        venue,
                        source,
                        abstract,
                        journal_ref,
                        doi,
                        paradedb.score(id) as rank
                    FROM papers
                    WHERE (title || ' ' || COALESCE(abstract, '')) @@@ $1
                    ORDER BY rank DESC
                    LIMIT $2
                """

                rows = await conn.fetch(sql, escaped_query, limit)

                results = []
                for row in rows:
                    # Parse authors (stored as array in PostgreSQL)
                    authors = row["authors"] or []
                    if isinstance(authors, str):
                        try:
                            authors = json.loads(authors)
                        except json.JSONDecodeError:
                            authors = [authors]

                    # Build URL based on source
                    source = row["source"] or "unknown"
                    if source == "arxiv":
                        url = f"https://arxiv.org/abs/{row['id']}"
                        # For arxiv, year is typically the publication year
                        published_date = str(row["year"]) if row["year"] else "N/A"
                    elif source == "dblp":
                        url = f"https://dblp.org/rec/{row['id']}.html"
                        published_date = str(row["year"]) if row["year"] else "N/A"
                    else:
                        url = row["doi"] or f"https://arxiv.org/abs/{row['id']}"
                        published_date = str(row["year"]) if row["year"] else "N/A"

                    results.append(
                        SearchResult(
                            title=row["title"],
                            authors=authors if isinstance(authors, list) else [],
                            published_date=published_date,
                            venue=row["venue"] or row["journal_ref"] or "N/A",
                            abstract=row["abstract"] or "N/A",
                            url=url,
                            source=f"local_db_{source}",
                        )
                    )

                return results

        except Exception as e:
            logger.error(f"[LocalDBSearch] Database query failed: {e}")
            raise
