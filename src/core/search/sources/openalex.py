"""OpenAlex search tool implementation."""
import httpx

from ...config import TOKEN_BUCKET_RATE_OPENALEX
from ...logger import logger
from ..base import SearchResult, SearchTool


class OpenAlexSearch(SearchTool):
    """Tool to search OpenAlex."""

    token_bucket_rate = TOKEN_BUCKET_RATE_OPENALEX

    async def _perform_asearch(self, query: str, limit: int) -> list[SearchResult]:
        logger.info(f"Searching OpenAlex (Async) for: {query}")
        url = "https://api.openalex.org/works"
        params = {"search": query, "per_page": limit}
        headers = {"User-Agent": "ValiRef/1.0 (mailto:your_email@example.com)"}

        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            return self._parse_openalex_response(response.json())

    def _parse_openalex_response(self, data: dict) -> list[SearchResult]:
        results = data.get("results", [])
        output = []
        for item in results:
            authors = []
            for authorship in item.get("authorships", []):
                author = authorship.get("author", {})
                if "display_name" in author:
                    authors.append(author["display_name"])

            venue = "N/A"
            primary_location = item.get("primary_location")
            if primary_location and primary_location.get("source"):
                venue = primary_location["source"].get("display_name", "N/A")

            output.append(
                SearchResult(
                    title=item.get("title", "N/A"),
                    authors=authors,
                    published_date=str(item.get("publication_year", "N/A")),
                    venue=venue,
                    abstract="N/A",
                    url=item.get("doi") or item.get("id"),
                    source="openalex",
                )
            )
        return output
