"""ArXiv search tool implementation."""
import xml.etree.ElementTree as ET

import httpx

from ...config import TOKEN_BUCKET_RATE_ARXIV
from ...logger import logger
from ..base import SearchResult, SearchTool


class ArxivSearch(SearchTool):
    """Tool to search ArXiv for papers."""

    token_bucket_rate = TOKEN_BUCKET_RATE_ARXIV

    async def _perform_asearch(self, query: str, limit: int) -> list[SearchResult]:
        """Async implementation of ArXiv search using httpx and XML parsing."""

        logger.info(f"Searching ArXiv (Async) for: {query}")
        url = "https://export.arxiv.org/api/query"
        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": limit,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()

            # Parse XML response
            try:
                root = ET.fromstring(response.content)
                # Define namespace
                ns = {
                    "atom": "http://www.w3.org/2005/Atom",
                    "arxiv": "http://arxiv.org/schemas/atom",
                }

                results = []
                for entry in root.findall("atom:entry", ns):
                    title = entry.find("atom:title", ns).text.strip().replace("\n", " ")
                    summary = (
                        entry.find("atom:summary", ns).text.strip().replace("\n", " ")
                    )
                    published = entry.find("atom:published", ns).text[:10]

                    authors = [
                        a.find("atom:name", ns).text
                        for a in entry.findall("atom:author", ns)
                    ]

                    pdf_url = None
                    for link in entry.findall("atom:link", ns):
                        if link.attrib.get("title") == "pdf":
                            pdf_url = link.attrib.get("href")

                    arxiv_id = entry.find("atom:id", ns).text.split("/abs/")[-1]

                    results.append(
                        SearchResult(
                            title=title,
                            authors=authors,
                            published_date=published,
                            abstract=summary,
                            url=pdf_url or f"http://arxiv.org/abs/{arxiv_id}",
                            venue="ArXiv",
                            source="arxiv",
                        )
                    )
                return results
            except Exception as e:
                logger.error(f"Error parsing ArXiv XML: {e}")
                return []
