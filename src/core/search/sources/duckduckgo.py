"""DuckDuckGo search tool implementation."""
from ddgs import DDGS

from ...config import DUCKDUCKGO_SEARCH_LIMIT, TOKEN_BUCKET_RATE_DUCKDUCKGO
from ...logger import logger
from ..base import SearchResult, SearchTool, run_in_executor_cancellable


class DuckDuckGoSearch(SearchTool):
    """Tool to search the web using DuckDuckGo."""

    token_bucket_rate = TOKEN_BUCKET_RATE_DUCKDUCKGO

    async def _perform_asearch(self, query: str, limit: int) -> list[SearchResult]:
        """Async wrapper for synchronous DuckDuckGo search with cancellation support."""
        return await run_in_executor_cancellable(
            self._perform_search_sync, query, limit
        )

    def _perform_search_sync(
        self, query: str, limit: int = DUCKDUCKGO_SEARCH_LIMIT
    ) -> list[SearchResult]:
        logger.info("Searching DuckDuckGo", query=query)
        results = []
        with DDGS() as ddgs:
            ddgs_gen = ddgs.text(query, max_results=limit)
            for r in ddgs_gen:
                results.append(
                    SearchResult(
                        title=r.get("title", "N/A"),
                        authors=[],  # DDG search results don't usually have authors
                        published_date="N/A",
                        venue="Web",
                        abstract=r.get("body", "N/A"),
                        url=r.get("href", "N/A"),
                        source="duckduckgo",
                    )
                )
        return results
