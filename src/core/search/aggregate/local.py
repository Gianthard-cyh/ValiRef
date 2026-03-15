"""Local aggregate search using ParadeDB."""
from ...logger import logger
from ..base import SearchResult
from ..sources.local_db import LocalDBSearch
from .utils import prune_search_result


class LocalAggregateSearch:
    """
    Local aggregate search that only queries local ParadeDB.
    """

    def __init__(self):
        self.tool = LocalDBSearch()

    def get_tool_description(self) -> str:
        return (
            "Search local ParadeDB database for papers matching the query. "
            "Returns results from local_db_arxiv, local_db_dblp sources. "
            "Local database results are authoritative and indicate the paper exists."
        )

    async def asearch(
        self, query: str, sources: list[str] = None, limit: int = 5
    ) -> list[dict]:
        """
        Search local database.

        Args:
            query: The search query.
            sources: Ignored for local search (kept for compatibility).
            limit: Max results to return.

        Returns:
            List of search result dictionaries.
        """
        logger.info(f"Local aggregate search for '{query}'")

        results = await self.tool.asearch(query, limit=limit)

        # Prune attributes to limit context length
        pruned_results = [prune_search_result(item) for item in results]

        return [r.model_dump() for r in pruned_results]
