"""OpenReview search tool implementation."""
import time

import httpx

from ...config import TOKEN_BUCKET_RATE_OPENREVIEW
from ...logger import logger
from ..base import SearchResult, SearchTool


class OpenReviewSearch(SearchTool):
    """Tool to search OpenReview."""

    token_bucket_rate = TOKEN_BUCKET_RATE_OPENREVIEW

    async def _perform_asearch(self, query: str, limit: int) -> list[SearchResult]:
        """Async implementation of OpenReview search using httpx."""
        logger.info(f"Searching OpenReview (Async) for: {query}")

        # OpenReview API v2 search endpoint
        # Based on typical usage: GET /notes/search?term={query}&limit={limit}&source=forum
        url = "https://api2.openreview.net/notes/search"
        params = {"term": query, "limit": limit, "source": "forum"}

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            notes = data.get("notes", [])
            output = []
            for note in notes:
                content = note.get("content", {})
                title = content.get("title", {}).get("value", "N/A")
                authors = content.get("authors", {}).get("value", [])
                abstract = content.get("abstract", {}).get("value", "N/A")

                # Convert timestamp if available
                cdate = note.get("cdate")
                published = "N/A"
                if cdate:
                    published = time.strftime("%Y-%m-%d", time.gmtime(cdate / 1000))

                output.append(
                    SearchResult(
                        title=title,
                        authors=authors,
                        published_date=published,
                        venue="OpenReview",
                        abstract=abstract,
                        url=f"https://openreview.net/forum?id={note.get('id')}",
                        source="openreview_v2",
                    )
                )
            return output
