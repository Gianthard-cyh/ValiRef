import time
import random
import threading
import asyncio
from typing import List, Dict, Callable
import xml.etree.ElementTree as ET
from pydantic import BaseModel, Field
from scholarly import scholarly
from ratelimit import limits, sleep_and_retry
from .config import (
    SCHOLAR_RATE_LIMIT_CALLS,
    SCHOLAR_RATE_LIMIT_PERIOD,
    ARXIV_RATE_LIMIT_DELAY,
    SCHOLAR_SEARCH_LIMIT,
    SEMANTIC_SCHOLAR_API_KEY,
    OPENALEX_SEARCH_LIMIT,
    DUCKDUCKGO_SEARCH_LIMIT,
)
from .logger import logger
import openreview
import httpx
from semanticscholar import SemanticScholar
from duckduckgo_search import DDGS


class SearchResult(BaseModel):
    """
    Unified schema for search results.
    """

    title: str = Field(..., description="Title of the paper")
    authors: List[str] = Field(default_factory=list, description="List of authors")
    published_date: str = Field("N/A", description="Publication date or year")
    abstract: str = Field("N/A", description="Abstract of the paper")
    venue: str = Field("N/A", description="Venue or Journal")
    url: str = Field(..., description="URL to the paper or PDF")
    source: str = Field(..., description="Source of the result")


class SearchTool:
    """
    Base class for search tools with thread-safe and async-aware backoff mechanism.
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
                    "lock": threading.Lock(),
                    "backoff_until": 0,
                }

    @property
    def _state(self):
        return self._rate_limit_states[self.__class__]

    async def asearch(self, query: str, limit: int = 5) -> List[SearchResult]:
        """Asynchronous search method."""
        return await self._asearch_with_retry(self._perform_asearch, query, limit)

    async def _perform_asearch(self, query: str, limit: int) -> List[SearchResult]:
        """
        Implement asynchronous search logic.
        Subclasses should override this method.
        """
        raise NotImplementedError

    async def _asearch_with_retry(
        self, func: Callable, *args, **kwargs
    ) -> List[SearchResult]:
        """
        Executes the search function with exponential backoff (async version).
        """
        retries = 3
        base_backoff = 2.0

        for i in range(retries + 1):
            state = self._state
            # Check shared state (still using thread lock as it might be shared with sync threads)
            with state["lock"]:
                wait_time = state["backoff_until"] - time.time()

            if wait_time > 0:
                sleep_duration = wait_time + random.uniform(0.1, 0.5)
                logger.info(
                    f"[{self.__class__.__name__}] Global backoff active. Sleeping {sleep_duration:.2f}s..."
                )
                await asyncio.sleep(sleep_duration)

            try:
                return await func(*args, **kwargs)
            except asyncio.CancelledError:
                logger.info(
                    f"[{self.__class__.__name__}] Task cancelled. Exiting retry loop."
                )
                raise
            except Exception as e:
                if i == retries:
                    logger.error(
                        f"[{self.__class__.__name__}] Failed after {retries} retries: {str(e)}"
                    )
                    return []

                backoff_duration = (base_backoff * (2**i)) + random.uniform(0, 1)

                with state["lock"]:
                    new_backoff_until = time.time() + backoff_duration
                    if new_backoff_until > state["backoff_until"]:
                        state["backoff_until"] = new_backoff_until

                logger.warning(
                    f"[{self.__class__.__name__}] Error: {str(e)}. Retrying in {backoff_duration:.2f}s..."
                )
                await asyncio.sleep(backoff_duration)
        return []


class ArxivSearch(SearchTool):
    """Tool to search ArXiv for papers."""
    
    def __init__(self):
        super().__init__()
        # Ensure rate limit state has last_request_time
        with self._state['lock']:
            if 'last_request_time' not in self._state:
                self._state['last_request_time'] = 0.0

    async def _perform_asearch(self, query: str, limit: int) -> List[SearchResult]:
        """Async implementation of ArXiv search using httpx and XML parsing."""
        
        # Rate limiting logic
        state = self._state
        delay_needed = 0.0
        
        with state['lock']:
            now = time.time()
            # If last_request_time is in the future, we must wait until then
            # We want to ensure 4s gap between START of requests
            
            last_request_time = state.get('last_request_time', 0.0)
            
            # If the last request was too recent (or scheduled in future), we wait
            if now < last_request_time + ARXIV_RATE_LIMIT_DELAY:
                # We need to wait until (last + delay)
                target_time = last_request_time + ARXIV_RATE_LIMIT_DELAY
                delay_needed = target_time - now
                
                # We claim the slot at target_time
                state['last_request_time'] = target_time
            else:
                # We can start immediately, so we claim "now"
                state['last_request_time'] = now
                
        if delay_needed > 0:
            logger.info(f"ArXiv rate limit active. Sleeping for {delay_needed:.2f}s...")
            await asyncio.sleep(delay_needed)
            
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


class ScholarlySearch(SearchTool):
    """Tool to search Google Scholar using `scholarly` library (free)."""

    @sleep_and_retry
    @limits(calls=SCHOLAR_RATE_LIMIT_CALLS, period=SCHOLAR_RATE_LIMIT_PERIOD)
    def _search_with_rate_limit(self, query: str):
        logger.info(f"Searching Google Scholar for: {query}")
        return scholarly.search_pubs(query)

    async def _perform_asearch(self, query: str, limit: int) -> List[SearchResult]:
        """Async wrapper for synchronous scholarly search."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._perform_search_sync, query, limit)

    def _perform_search_sync(
        self, query: str, limit: int = SCHOLAR_SEARCH_LIMIT
    ) -> List[SearchResult]:
        search_query = self._search_with_rate_limit(query)
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


class SemanticScholarSearch(SearchTool):
    """Tool to search Semantic Scholar."""

    def __init__(self):
        super().__init__()
        self.sch = SemanticScholar(api_key=SEMANTIC_SCHOLAR_API_KEY, timeout=10)

    async def _perform_asearch(self, query: str, limit: int) -> List[SearchResult]:
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

        try:
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
        except Exception as e:
            logger.error(f"Error searching Semantic Scholar: {e}")
            return []


class OpenReviewSearch(SearchTool):
    """Tool to search OpenReview."""

    def __init__(self):
        super().__init__()
        try:
            self.client = openreview.api.OpenReviewClient(
                baseurl="https://api2.openreview.net"
            )
        except Exception as e:
            logger.warning(f"Failed to initialize OpenReview client: {e}")
            self.client = None

    async def _perform_asearch(self, query: str, limit: int) -> List[SearchResult]:
        """Async implementation of OpenReview search using httpx."""
        logger.info(f"Searching OpenReview (Async) for: {query}")

        # OpenReview API v2 search endpoint
        # Based on typical usage: GET /notes/search?term={query}&limit={limit}&source=forum
        url = "https://api2.openreview.net/notes/search"
        params = {"term": query, "limit": limit, "source": "forum"}

        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

                notes = data.get("notes", [])
                output = []
                for note in notes:
                    content = note.get("content", {})
                    title = content.get("title", {}).get("value", "N/A")
                    authors = content.get("authors", {}).get("value", [])
                    abstract = content.get("abstract", {}).get("value", "N/A")

                    # Convert timestamp if available
                    cdate = note.get("cdate")
                    published = "N/A"
                    if cdate:
                        published = time.strftime("%Y-%m-%d", time.gmtime(cdate / 1000))

                    output.append(
                        SearchResult(
                            title=title,
                            authors=authors,
                            published_date=published,
                            venue="OpenReview",
                            abstract=abstract,
                            url=f"https://openreview.net/forum?id={note.get('id')}",
                            source="openreview_v2",
                        )
                    )
                return output
        except Exception as e:
            logger.error(f"Error searching OpenReview: {e}")
            return []


class OpenAlexSearch(SearchTool):
    """Tool to search OpenAlex."""

    # We override perform_search for sync (still using requests for backward compat if needed)
    def _perform_search(
        self, query: str, limit: int = OPENALEX_SEARCH_LIMIT
    ) -> List[Dict]:
        logger.info(f"Searching OpenAlex for: {query}")
        url = "https://api.openalex.org/works"
        params = {"search": query, "per_page": limit}
        headers = {"User-Agent": "ValiRef/1.0 (mailto:your_email@example.com)"}
        response = httpx.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        return self._parse_openalex_response(response.json())

    # We override perform_asearch for native async using httpx
    async def _perform_asearch(self, query: str, limit: int) -> List[SearchResult]:
        logger.info(f"Searching OpenAlex (Async) for: {query}")
        url = "https://api.openalex.org/works"
        params = {"search": query, "per_page": limit}
        headers = {"User-Agent": "ValiRef/1.0 (mailto:your_email@example.com)"}

        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            return self._parse_openalex_response(response.json())

    def _parse_openalex_response(self, data: Dict) -> List[SearchResult]:
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


class DuckDuckGoSearch(SearchTool):
    """Tool to search the web using DuckDuckGo."""

    async def _perform_asearch(self, query: str, limit: int) -> List[SearchResult]:
        """Async wrapper for synchronous DuckDuckGo search."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._perform_search_sync, query, limit)

    def _perform_search_sync(
        self, query: str, limit: int = DUCKDUCKGO_SEARCH_LIMIT
    ) -> List[SearchResult]:
        logger.info(f"Searching DuckDuckGo for: {query}")
        try:
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
        except Exception as e:
            logger.error(f"Error searching DuckDuckGo: {e}")
            return []


class AggregateSearch:
    """
    Aggregate search tool that queries multiple sources concurrently.
    """

    def __init__(self):
        self.tools = {
            "arxiv": ArxivSearch(),
            # "google_scholar": ScholarlySearch(),
            # "semantic_scholar": SemanticScholarSearch(),
            "openreview": OpenReviewSearch(),
            "openalex": OpenAlexSearch(),
            "duckduckgo": DuckDuckGoSearch(),
        }

    async def asearch(
        self, query: str, sources: List[str] = None, limit: int = 5
    ) -> List[SearchResult]:
        """
        Search multiple sources concurrently.

        Args:
            query: The search query.
            sources: List of sources to search. Defaults to ["arxiv", "openalex", "openreview"].
                     Available: "arxiv", "google_scholar", "semantic_scholar", "openreview", "openalex", "duckduckgo"
            limit: Max results per source.
        """
        if sources is None:
            sources = ["arxiv", "openalex", "openreview"]

        valid_sources = [s for s in sources if s in self.tools]
        if not valid_sources:
            logger.warning(f"No valid sources provided in {sources}. Using default.")
            valid_sources = ["arxiv", "openalex"]

        logger.info(f"Aggregate search for '{query}' on {valid_sources}")

        tasks: List[asyncio.Task[List[SearchResult]]] = []
        for source in valid_sources:
            tool = self.tools[source]
            tasks.append(asyncio.create_task(tool.asearch(query, limit=limit)))

        results_list: List[Union[List[SearchResult], Exception]] = await asyncio.gather(
            *tasks, return_exceptions=True
        )

        final_results: List[SearchResult] = []
        for i, result in enumerate(results_list):
            source_name = valid_sources[i]
            if isinstance(result, Exception):
                logger.error(f"Error searching {source_name}: {result}")
            elif result:
                final_results.extend(result)

        # Simple deduplication by title (normalized)
        seen_titles = set()
        unique_results: List[SearchResult] = []
        for item in final_results:
            title_norm = item.title.lower().strip()
            if title_norm and title_norm not in seen_titles:
                seen_titles.add(title_norm)
                
                # Prune attributes to limit context length
                if len(item.title) > 200:
                    item.title = item.title[:200] + "..."
                if len(item.abstract) > 500:
                    item.abstract = item.abstract[:500] + "..."
                if len(item.authors) > 15:
                    item.authors = item.authors[:15]
                    item.authors.append("et al.")
                
                unique_results.append(item)
                
        dicts = [item.model_dump() for item in unique_results]
        return dicts
