from typing import List, Dict, Any
import arxiv
from scholarly import scholarly
from ratelimit import limits, sleep_and_retry
from .config import (
    SCHOLAR_RATE_LIMIT_CALLS,
    SCHOLAR_RATE_LIMIT_PERIOD,
    ARXIV_SEARCH_LIMIT,
    SCHOLAR_SEARCH_LIMIT,
    SEMANTIC_SCHOLAR_API_KEY,
    SEMANTIC_SCHOLAR_SEARCH_LIMIT,
    OPENREVIEW_SEARCH_LIMIT,
    OPENALEX_SEARCH_LIMIT,
)
from .logger import logger
import openreview
import requests
from semanticscholar import SemanticScholar


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
            client = arxiv.Client()
            search = arxiv.Search(
                query=query, max_results=limit, sort_by=arxiv.SortCriterion.Relevance
            )

            results = []
            for result in client.results(search):
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


class SemanticScholarSearch(SearchTool):
    """
    Tool to search Semantic Scholar.
    """

    def __init__(self):
        self.sch = SemanticScholar(api_key=SEMANTIC_SCHOLAR_API_KEY, timeout=10)

    def search(
        self, query: str, limit: int = SEMANTIC_SCHOLAR_SEARCH_LIMIT
    ) -> List[Dict]:
        logger.info(f"Searching Semantic Scholar for: {query} (limit={limit})")
        try:
            results = self.sch.search_paper(query, limit=limit, bulk=True)
            output = []
            for item in results:
                output.append(
                    {
                        "title": item.title,
                        "authors": [a.name for a in item.authors],
                        "published": str(item.year) if item.year else "N/A",
                        "venue": item.venue if item.venue else "N/A",
                        "abstract": item.abstract if item.abstract else "N/A",
                        "link": item.url,
                        "source": "semantic_scholar",
                    }
                )
            return output
        except Exception as e:
            logger.error(f"Semantic Scholar search failed: {e}")
            return []


class OpenReviewSearch(SearchTool):
    """
    Tool to search OpenReview.
    """

    def __init__(self):
        # Only initialize v2 client, as v1 is legacy
        try:
            self.client = openreview.api.OpenReviewClient(baseurl="https://api2.openreview.net")
        except Exception as e:
            logger.warning(f"Failed to initialize OpenReview client: {e}")
            self.client = None

    def search(self, query: str, limit: int = OPENREVIEW_SEARCH_LIMIT) -> List[Dict]:
        logger.info(f"Searching OpenReview for: {query}")
        if not self.client:
            return []
            
        try:
            # Use search_notes for fuzzy/keyword search (Elasticsearch)
            # This is more robust than get_notes(content={'title': ...}) which requires exact match
            notes = self.client.search_notes(term=query, limit=limit, source='forum')
            
            output = []
            for note in notes:
                content = note.content
                # v2 content values are usually wrapped in 'value'
                title = content.get("title", {}).get("value", "N/A")
                authors = content.get("authors", {}).get("value", [])
                abstract = content.get("abstract", {}).get("value", "N/A")
                
                output.append({
                    "title": title,
                    "authors": authors,
                    "published": str(note.cdate) if note.cdate else "N/A",
                    "venue": "OpenReview",
                    "abstract": abstract,
                    "link": f"https://openreview.net/forum?id={note.id}",
                    "source": "openreview_v2"
                })
            return output
            
        except Exception as e:
            logger.error(f"OpenReview search failed: {e}")
            return []


class OpenAlexSearch(SearchTool):
    """
    Tool to search OpenAlex.
    """

    def search(self, query: str, limit: int = OPENALEX_SEARCH_LIMIT) -> List[Dict]:
        logger.info(f"Searching OpenAlex for: {query}")
        try:
            url = "https://api.openalex.org/works"
            params = {
                "search": query,
                "per_page": limit,
            }
            # Adding a polite user agent
            headers = {
                "User-Agent": "ValiRef/1.0 (mailto:your_email@example.com)"
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            results = data.get("results", [])
            output = []

            for item in results:
                # Extract authors
                authors = []
                for authorship in item.get("authorships", []):
                    author = authorship.get("author", {})
                    if "display_name" in author:
                        authors.append(author["display_name"])
                
                # Extract venue
                venue = "N/A"
                primary_location = item.get("primary_location")
                if primary_location and primary_location.get("source"):
                    venue = primary_location["source"].get("display_name", "N/A")

                output.append(
                    {
                        "title": item.get("title", "N/A"),
                        "authors": authors,
                        "published": str(item.get("publication_year", "N/A")),
                        "venue": venue,
                        "abstract": "N/A", # OpenAlex uses inverted index for abstracts, skipping for now
                        "link": item.get("doi") or item.get("id"),
                        "source": "openalex",
                    }
                )
            return output
        except Exception as e:
            logger.error(f"OpenAlex search failed: {e}")
            return []
