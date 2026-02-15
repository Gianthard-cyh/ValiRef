from typing import List, Dict
import arxiv
from scholarly import scholarly
from ratelimit import limits, sleep_and_retry
from .config import (
    SCHOLAR_RATE_LIMIT_CALLS,
    SCHOLAR_RATE_LIMIT_PERIOD,
    ARXIV_SEARCH_LIMIT,
    SCHOLAR_SEARCH_LIMIT,
)
from .logger import logger


class SearchTool:
    """
    Base class for search tools.
    """

    def search(self, query: str, limit: int = 5) -> List[Dict]:
        raise NotImplementedError


class ArxivSearch(SearchTool):
    """
    Tool to search ArXiv for papers.
    """

    def search(self, query: str, limit: int = ARXIV_SEARCH_LIMIT) -> List[Dict]:
        """
        Search ArXiv for papers matching the query.
        Returns a list of dictionaries with paper details.
        """
        try:
            search = arxiv.Search(
                query=query, max_results=limit, sort_by=arxiv.SortCriterion.Relevance
            )

            results = []
            for result in search.results():
                results.append(
                    {
                        "title": result.title,
                        "authors": [a.name for a in result.authors],
                        "published": result.published.strftime("%Y-%m-%d"),
                        "summary": result.summary,
                        "pdf_url": result.pdf_url,
                        "arxiv_id": result.entry_id.split("/")[-1],
                        "source": "arxiv",
                    }
                )
            return results
        except Exception as e:
            logger.error(f"ArXiv search failed: {e}")
            return []


class ScholarlySearch(SearchTool):
    """
    Tool to search Google Scholar using `scholarly` library (free).
    Includes rate limiting to avoid blocking using `ratelimit` library.
    """

    # Limit to 1 call every 20 seconds
    @sleep_and_retry
    @limits(calls=SCHOLAR_RATE_LIMIT_CALLS, period=SCHOLAR_RATE_LIMIT_PERIOD)
    def _search_with_rate_limit(self, query: str):
        logger.info(f"Searching Google Scholar for: {query}")
        return scholarly.search_pubs(query)

    def search(self, query: str, limit: int = SCHOLAR_SEARCH_LIMIT) -> List[Dict]:
        """
        Search Google Scholar for papers matching the query.
        """
        try:
            search_query = self._search_with_rate_limit(query)
            results = []

            for _ in range(limit):
                try:
                    item = next(search_query)
                    bib = item.get("bib", {})
                    results.append(
                        {
                            "title": bib.get("title"),
                            "authors": bib.get(
                                "author", []
                            ),  # scholarly returns list of strings
                            "published": bib.get("pub_year", "N/A"),
                            "venue": bib.get("venue", "N/A"),
                            "abstract": bib.get("abstract", "N/A"),
                            "link": item.get("pub_url", "N/A"),
                            "source": "google_scholar_free",
                        }
                    )
                except StopIteration:
                    break
                except Exception as e:
                    logger.warning(f"Error parsing scholarly result: {e}")
                    continue

            return results
        except Exception as e:
            logger.error(f"Scholarly search failed: {e}")
            return []
