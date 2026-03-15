"""Online aggregate search using external APIs."""
import asyncio
from typing import Union

from ...logger import logger
from ..base import SearchResult
from ..sources.arxiv import ArxivSearch
from ..sources.duckduckgo import DuckDuckGoSearch
from ..sources.openalex import OpenAlexSearch
from ..sources.openreview import OpenReviewSearch
from .utils import prune_search_result


class OnlineAggregateSearch:
    """
    Online aggregate search that queries multiple external API sources.
    """

    def __init__(self):
        self.tools = {
            "arxiv": ArxivSearch(),
            "openreview": OpenReviewSearch(),
            "openalex": OpenAlexSearch(),
            "duckduckgo": DuckDuckGoSearch(),
        }

    def get_tool_description(self) -> str:
        return (
            "Search multiple online sources concurrently for papers matching the query. "
            "Sources can be a list of: 'arxiv', 'openreview', 'openalex', 'duckduckgo'. "
            "Returns a combined list of paper details."
        )

    async def asearch(
        self, query: str, sources: list[str] = None, limit: int = 5
    ) -> list[dict]:
        """
        Search multiple online sources concurrently.

        Args:
            query: The search query.
            sources: List of sources to search.
            limit: Max results per source.

        Returns:
            List of search result dictionaries.
        """
        if sources is None:
            sources = ["arxiv", "openalex", "openreview"]

        valid_sources = [s for s in sources if s in self.tools]
        if not valid_sources:
            logger.warning(f"No valid sources provided in {sources}. Using default.")
            valid_sources = ["arxiv", "openalex"]

        logger.info(f"Online aggregate search for '{query}' on {valid_sources}")

        tasks: list[asyncio.Task[list[SearchResult]]] = []
        for source in valid_sources:
            tool = self.tools[source]

            async def search_with_timeout(tool=tool, query=query, limit=limit):
                return await asyncio.wait_for(
                    tool.asearch(query, limit=limit), timeout=8.0
                )

            tasks.append(asyncio.create_task(search_with_timeout()))

        results_list: list[Union[list[SearchResult], Exception]] = await asyncio.gather(
            *tasks, return_exceptions=True
        )

        final_results: list[SearchResult] = []
        failed_sources: list[str] = []

        for i, result in enumerate(results_list):
            source_name = valid_sources[i]
            if isinstance(result, asyncio.TimeoutError):
                logger.warning(f"Timeout searching {source_name}")
                failed_sources.append(source_name)
            elif isinstance(result, Exception):
                logger.error(f"Error searching {source_name}: {result}")
                failed_sources.append(source_name)
            elif result:
                final_results.extend(result)
            else:
                failed_sources.append(source_name)

        # Simple deduplication by title (normalized)
        seen_titles = set()
        unique_results: list[SearchResult] = []
        for item in final_results:
            title_norm = item.title.lower().strip()
            if title_norm and title_norm not in seen_titles:
                seen_titles.add(title_norm)
                unique_results.append(prune_search_result(item))

        # Add markers for failed sources
        for source in failed_sources:
            unique_results.append(
                SearchResult(
                    title=f"[Source Unavailable: {source}]",
                    authors=[],
                    published_date="N/A",
                    venue="N/A",
                    abstract=f"The {source} source did not return any results.",
                    url="N/A",
                    source=f"{source}_unavailable",
                )
            )

        return [item.model_dump() for item in unique_results]
