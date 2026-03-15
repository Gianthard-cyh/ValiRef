"""Google Scholar search tool implementation."""
from scholarly import scholarly

from ...config import SCHOLAR_SEARCH_LIMIT, TOKEN_BUCKET_RATE_SCHOLAR
from ...logger import logger
from ..base import SearchResult, SearchTool, run_in_executor_cancellable


class ScholarlySearch(SearchTool):
    """Tool to search Google Scholar using `scholarly` library (free)."""

    token_bucket_rate = TOKEN_BUCKET_RATE_SCHOLAR

    async def _perform_asearch(self, query: str, limit: int) -> list[SearchResult]:
        """Async wrapper for synchronous scholarly search with cancellation support."""
        return await run_in_executor_cancellable(
            self._perform_search_sync, query, limit
        )

    def _perform_search_sync(
        self, query: str, limit: int = SCHOLAR_SEARCH_LIMIT
    ) -> list[SearchResult]:
        logger.info(f"Searching Google Scholar for: {query}")
        search_query = scholarly.search_pubs(query)
        results = []
        for _ in range(limit):
            try:
                item = next(search_query)
                bib = item.get("bib", {})
                results.append(
                    SearchResult(
                        title=bib.get("title", ""),
                        authors=bib.get("author", []),
                        published_date=str(bib.get("pub_year", "N/A")),
                        venue=str(bib.get("venue", "N/A")),
                        abstract=str(bib.get("abstract", "N/A")),
                        url=str(item.get("pub_url", "N/A")),
                        source="google_scholar_free",
                    )
                )
            except StopIteration:
                break
            except Exception as e:
                logger.warning(f"Error parsing scholarly result: {e}")
                continue
        return results
