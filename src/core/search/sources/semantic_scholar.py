"""Semantic Scholar search tool implementation."""
import httpx

from ...config import SEMANTIC_SCHOLAR_API_KEY, TOKEN_BUCKET_RATE_SEMANTIC_SCHOLAR
from ...logger import logger
from ..base import SearchResult, SearchTool


class SemanticScholarSearch(SearchTool):
    """Tool to search Semantic Scholar."""

    token_bucket_rate = TOKEN_BUCKET_RATE_SEMANTIC_SCHOLAR

    async def _perform_asearch(self, query: str, limit: int) -> list[SearchResult]:
        """Async implementation of Semantic Scholar search using httpx."""

        logger.info(f"Searching Semantic Scholar (Async) for: {query} (limit={limit})")
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {
            "query": query,
            "limit": limit,
            "fields": "title,authors,year,venue,abstract,url",
        }
        headers = {}
        if SEMANTIC_SCHOLAR_API_KEY:
            headers["x-api-key"] = SEMANTIC_SCHOLAR_API_KEY

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get("data", []):
                authors = [a.get("name") for a in item.get("authors", [])]
                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        authors=authors,
                        published_date=(
                            str(item.get("year")) if item.get("year") else "N/A"
                        ),
                        venue=item.get("venue") or "N/A",
                        abstract=item.get("abstract") or "N/A",
                        url=item.get("url") or "N/A",
                        source="semantic_scholar",
                    )
                )
            return results
