import time
from functools import wraps
import random
import threading
from typing import List, Dict, Callable, Any
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
    Base class for search tools with thread-safe backoff mechanism.
    Maintains global state per subclass to handle rate limits across all instances.
    """
    # Global state for rate limiting, shared across all instances of the same tool class
    _rate_limit_states = {}
    _state_lock = threading.Lock()

    def __init__(self):
        # Initialize state for this class if not exists
        with self._state_lock:
            if self.__class__ not in self._rate_limit_states:
                self._rate_limit_states[self.__class__] = {
                    'lock': threading.Lock(),
                    'backoff_until': 0
                }

    @property
    def _state(self):
        return self._rate_limit_states[self.__class__]

    def search(self, query: str, limit: int = 5) -> List[Dict]:
        return self._search_with_retry(self._perform_search, query, limit)

    def _perform_search(self, query: str, limit: int) -> List[Dict]:
        raise NotImplementedError

    def _search_with_retry(self, func: Callable, *args, **kwargs) -> List[Dict]:
        """
        Executes the search function with exponential backoff and global (per-class)
        thread synchronization to handle rate limits in a concurrent environment.
        """
        retries = 3
        base_backoff = 2.0
        
        for i in range(retries + 1):
            # 1. Check if we need to wait for a global backoff triggered by another thread/instance
            # Use the shared lock for this tool class
            state = self._state
            with state['lock']:
                wait_time = state['backoff_until'] - time.time()
            
            if wait_time > 0:
                # Add slight jitter to prevent thundering herd when waking up
                sleep_duration = wait_time + random.uniform(0.1, 0.5)
                logger.info(f"[{self.__class__.__name__}] Global backoff active. Sleeping {sleep_duration:.2f}s...")
                time.sleep(sleep_duration)

            try:
                return func(*args, **kwargs)
            except Exception as e:
                # If this is the last attempt, log error and re-raise
                if i == retries:
                    logger.error(f"[{self.__class__.__name__}] Failed after {retries} retries: {str(e)}")
                    return []
                
                # Calculate next backoff
                backoff_duration = (base_backoff * (2 ** i)) + random.uniform(0, 1)
                
                # Update global backoff state so ALL threads/instances know to wait
                with state['lock']:
                    new_backoff_until = time.time() + backoff_duration
                    # Only extend the backoff if the new time is further in the future
                    if new_backoff_until > state['backoff_until']:
                        state['backoff_until'] = new_backoff_until
                
                logger.warning(f"[{self.__class__.__name__}] Error: {str(e)}. Retrying in {backoff_duration:.2f}s...")
                time.sleep(backoff_duration)
        
        return []


class ArxivSearch(SearchTool):
    """
    Tool to search ArXiv for papers.
    """
    def _perform_search(self, query: str, limit: int = ARXIV_SEARCH_LIMIT) -> List[Dict]:
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


class ScholarlySearch(SearchTool):
    """
    Tool to search Google Scholar using `scholarly` library (free).
    Includes rate limiting to avoid blocking using `ratelimit` library.
    """
    
    # We still use ratelimit for proactive limiting
    @sleep_and_retry
    @limits(calls=SCHOLAR_RATE_LIMIT_CALLS, period=SCHOLAR_RATE_LIMIT_PERIOD)
    def _search_with_rate_limit(self, query: str):
        logger.info(f"Searching Google Scholar for: {query}")
        return scholarly.search_pubs(query)

    def _perform_search(self, query: str, limit: int = SCHOLAR_SEARCH_LIMIT) -> List[Dict]:
        search_query = self._search_with_rate_limit(query)
        results = []

        for _ in range(limit):
            try:
                item = next(search_query)
                bib = item.get("bib", {})
                results.append(
                    {
                        "title": bib.get("title"),
                        "authors": bib.get("author", []),
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


class SemanticScholarSearch(SearchTool):
    """
    Tool to search Semantic Scholar.
    """

    def __init__(self):
        super().__init__()
        self.sch = SemanticScholar(api_key=SEMANTIC_SCHOLAR_API_KEY, timeout=10)

    def _perform_search(self, query: str, limit: int = SEMANTIC_SCHOLAR_SEARCH_LIMIT) -> List[Dict]:
        logger.info(f"Searching Semantic Scholar for: {query} (limit={limit})")
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


class OpenReviewSearch(SearchTool):
    """
    Tool to search OpenReview.
    """

    def __init__(self):
        super().__init__()
        # Only initialize v2 client, as v1 is legacy
        try:
            self.client = openreview.api.OpenReviewClient(baseurl="https://api2.openreview.net")
        except Exception as e:
            logger.warning(f"Failed to initialize OpenReview client: {e}")
            self.client = None

    def _perform_search(self, query: str, limit: int = OPENREVIEW_SEARCH_LIMIT) -> List[Dict]:
        logger.info(f"Searching OpenReview for: {query}")
        if not self.client:
            return []
            
        # Use search_notes for fuzzy/keyword search (Elasticsearch)
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


class OpenAlexSearch(SearchTool):
    """
    Tool to search OpenAlex.
    """

    def _perform_search(self, query: str, limit: int = OPENALEX_SEARCH_LIMIT) -> List[Dict]:
        logger.info(f"Searching OpenAlex for: {query}")
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
