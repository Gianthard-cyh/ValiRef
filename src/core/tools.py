import time
import random
import threading
import asyncio
from typing import List, Dict, Callable, Union
from datetime import datetime
import xml.etree.ElementTree as ET
from pydantic import BaseModel, Field
from scholarly import scholarly
from .config import (
    SCHOLAR_RATE_LIMIT_CALLS,
    SCHOLAR_RATE_LIMIT_PERIOD,
    ARXIV_RATE_LIMIT_DELAY,
    SEMANTIC_SCHOLAR_RATE_LIMIT_DELAY,
    SCHOLAR_SEARCH_LIMIT,
    SEMANTIC_SCHOLAR_API_KEY,
    OPENALEX_SEARCH_LIMIT,
    DUCKDUCKGO_SEARCH_LIMIT,
)
from .logger import logger
from .tool_monitor import tool_call_started, tool_call_ended
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
    
    # Subclasses should override this to set a specific rate limit delay
    rate_limit_delay = 0.0

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
        """Asynchronous search method with monitoring."""
        tool_name = self.__class__.__name__
        start_time = datetime.now()

        # 发布开始信号
        tool_call_started.send(
            'searchtool',
            tool_name=tool_name,
            query=query,
            start_time=start_time
        )

        try:
            results = await self._asearch_with_retry(self._perform_asearch, query, limit)

            end_time = datetime.now()
            duration_ms = (end_time - start_time).total_seconds() * 1000

            # 发布成功信号
            tool_call_ended.send(
                'searchtool',
                tool_name=tool_name,
                query=query,
                end_time=end_time,
                duration_ms=duration_ms,
                success=True,
                result_count=len(results)
            )
            return results

        except Exception as e:
            end_time = datetime.now()
            duration_ms = (end_time - start_time).total_seconds() * 1000

            # 发布失败信号
            tool_call_ended.send(
                'searchtool',
                tool_name=tool_name,
                query=query,
                end_time=end_time,
                duration_ms=duration_ms,
                success=False,
                result_count=0,
                error_type=e.__class__.__name__
            )
            raise

    async def _perform_asearch(self, query: str, limit: int) -> List[SearchResult]:
        """
        Implement asynchronous search logic.
        Subclasses should override this method.
        """
        raise NotImplementedError

    async def _wait_for_rate_limit(self):
        """
        Enforce a minimum delay between requests for this tool class using a leaky bucket algorithm.
        Ensures that requests are spaced out by at least `self.rate_limit_delay` seconds.
        """
        if self.rate_limit_delay <= 0:
            return

        state = self._state
        
        # Calculate how long to sleep OUTSIDE the lock
        # We only need the lock to update the shared state
        delay_needed = 0.0
        
        with state["lock"]:
            if "last_request_time" not in state:
                state["last_request_time"] = 0.0

            now = time.time()
            last_request_time = state["last_request_time"]
            
            # The next available slot is the later of:
            # 1. The current time (if we've been idle long enough)
            # 2. The previous request time + required delay
            next_slot = max(now, last_request_time + self.rate_limit_delay)
            
            delay_needed = next_slot - now
            
            # Update state to reserve this slot
            # IMPORTANT: We set last_request_time to next_slot, effectively "booking" it
            state["last_request_time"] = next_slot

        if delay_needed > 0:
            logger.info(
                f"[{self.__class__.__name__}] Rate limit active. Sleeping for {delay_needed:.2f}s..."
            )
            await asyncio.sleep(delay_needed)

    async def _asearch_with_retry(
        self, func: Callable, *args, **kwargs
    ) -> List[SearchResult]:
        """
        Executes the search function with exponential backoff and rate limiting (async version).
        """
        retries = 3
        base_backoff = 2.0

        for i in range(retries + 1):
            # 1. Check Rate Limit before making a request
            await self._wait_for_rate_limit()

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
            except httpx.HTTPStatusError as e:
                # Handle 429 Too Many Requests specifically
                if e.response.status_code == 429:
                    retry_after = e.response.headers.get("Retry-After")
                    if retry_after:
                        try:
                            backoff_duration = float(retry_after) + 1.0
                        except ValueError:
                            backoff_duration = (base_backoff * (2**i)) + random.uniform(1, 3)
                    else:
                        backoff_duration = (base_backoff * (2**i)) + random.uniform(5, 10) # Aggressive backoff for 429
                    
                    logger.warning(
                        f"[{self.__class__.__name__}] 429 Too Many Requests. Retrying in {backoff_duration:.2f}s..."
                    )
                else:
                    backoff_duration = (base_backoff * (2**i)) + random.uniform(0, 1)
                    logger.warning(
                         f"[{self.__class__.__name__}] HTTP Error {e.response.status_code}: {str(e)}. Retrying in {backoff_duration:.2f}s..."
                    )
                
                if i == retries:
                     logger.error(
                        f"[{self.__class__.__name__}] Failed after {retries} retries: {str(e)}"
                    )
                     return []

                with state["lock"]:
                    new_backoff_until = time.time() + backoff_duration
                    if new_backoff_until > state["backoff_until"]:
                        state["backoff_until"] = new_backoff_until
                
                await asyncio.sleep(backoff_duration)
                continue

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
    
    rate_limit_delay = ARXIV_RATE_LIMIT_DELAY

    def __init__(self):
        super().__init__()
        # Ensure rate limit state has last_request_time
        with self._state['lock']:
            if 'last_request_time' not in self._state:
                self._state['last_request_time'] = 0.0

    async def _perform_asearch(self, query: str, limit: int) -> List[SearchResult]:
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


class ScholarlySearch(SearchTool):
    """Tool to search Google Scholar using `scholarly` library (free)."""

    rate_limit_delay = SCHOLAR_RATE_LIMIT_PERIOD

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

    rate_limit_delay = SEMANTIC_SCHOLAR_RATE_LIMIT_DELAY

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
        failed_sources: List[str] = []

        for i, result in enumerate(results_list):
            source_name = valid_sources[i]
            if isinstance(result, Exception):
                logger.error(f"Error searching {source_name}: {result}")
                failed_sources.append(source_name)
            elif result:
                final_results.extend(result)
            else:
                # Empty result (not an error, but no data found)
                failed_sources.append(source_name)

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

        # Add markers for failed sources so the model knows which sources didn't return data
        for source in failed_sources:
            unique_results.append(
                SearchResult(
                    title=f"[Source Unavailable: {source}]",
                    authors=[],
                    published_date="N/A",
                    venue="N/A",
                    abstract=f"The {source} source did not return any results. This may be due to temporary unavailability or rate limiting.",
                    url="N/A",
                    source=f"{source}_unavailable",
                )
            )

        dicts = [item.model_dump() for item in unique_results]
        return dicts
