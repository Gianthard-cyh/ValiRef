import asyncio
import random
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union
import xml.etree.ElementTree as ET

import asyncpg
import httpx
from ddgs import DDGS
from pydantic import BaseModel, Field
from scholarly import scholarly
import json

from .search_cache import get_cache
from .config import (
    CIRCUIT_BREAKER_FAILURE_THRESHOLD,
    CIRCUIT_BREAKER_HALF_OPEN_CALLS,
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT,
    DUCKDUCKGO_SEARCH_LIMIT,
    SCHOLAR_SEARCH_LIMIT,
    SEMANTIC_SCHOLAR_API_KEY,
    TOKEN_BUCKET_BURST_SIZE,
    TOKEN_BUCKET_RATE_ARXIV,
    TOKEN_BUCKET_RATE_DUCKDUCKGO,
    TOKEN_BUCKET_RATE_OPENALEX,
    TOKEN_BUCKET_RATE_OPENREVIEW,
    TOKEN_BUCKET_RATE_SCHOLAR,
    TOKEN_BUCKET_RATE_SEMANTIC_SCHOLAR,
    DB_HOST,
    DB_PORT,
    DB_USER,
    DB_PASSWORD,
    DB_NAME,
)
from .logger import logger
from .search_queue import CircuitBreakerOpen, SearchTask, ToolRequestQueue
from .tool_monitor import tool_call_ended, tool_call_started


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


T = TypeVar("T")

# Shared thread pool for sync operations
_sync_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="search_sync_")


async def run_in_executor_cancellable(
    func: Callable[..., T], *args, timeout: Optional[float] = None
) -> T:
    """
    Run a synchronous function in a thread pool with proper cancellation support.

    Unlike raw asyncio.run_in_executor, this properly propagates CancelledError
    to the caller. The thread continues executing in background but the asyncio
    task is properly cancelled.
    """
    loop = asyncio.get_running_loop()

    # Submit to shared thread pool
    future = _sync_executor.submit(func, *args)

    try:
        if timeout:
            # Use wait_for for timeout support
            return await asyncio.wait_for(asyncio.wrap_future(future), timeout=timeout)
        else:
            return await asyncio.wrap_future(future)
    except asyncio.CancelledError:
        # Cancel the future if possible
        future.cancel()
        raise


class SearchTool:
    """
    Base class for search tools with queue-based rate limiting and circuit breaker protection.

    Each tool instance has its own ToolRequestQueue that provides:
    - Token bucket rate limiting (smooth request flow)
    - Circuit breaker pattern (fail-fast for failing services)
    - Proper cancellation handling (Ctrl+C safe)
    """

    # Subclasses should override this to set the token bucket rate
    token_bucket_rate = 1.0  # tokens per second

    def __init__(self):
        """Initialize the tool with its own request queue."""
        self._queue = ToolRequestQueue(
            tool_name=self.__class__.__name__,
            token_bucket_rate=self.token_bucket_rate,
            token_bucket_burst=TOKEN_BUCKET_BURST_SIZE,
            circuit_failure_threshold=CIRCUIT_BREAKER_FAILURE_THRESHOLD,
            circuit_recovery_timeout=CIRCUIT_BREAKER_RECOVERY_TIMEOUT,
            half_open_max_calls=CIRCUIT_BREAKER_HALF_OPEN_CALLS,
        )

    def search(self, query: str, limit: int = 5) -> List[Dict]:
        """
        Synchronous search method.

        Runs the async asearch() method using asyncio.run().
        Note: This cannot be called from within an existing async event loop.

        Args:
            query: The search query
            limit: Maximum number of results to return

        Returns:
            List of result dictionaries
        """
        return asyncio.run(self.asearch(query, limit))

    async def asearch(self, query: str, limit: int = 5) -> List[SearchResult]:
        """
        Asynchronous search method with caching, rate limiting and monitoring.

        Args:
            query: The search query
            limit: Maximum number of results to return

        Returns:
            List of SearchResult objects
        """
        tool_name = self.__class__.__name__

        # Check cache first
        cache = get_cache()
        cached_data = cache.get(tool_name, query, limit)
        if cached_data is not None:
            logger.info(f"[{tool_name}] Cache hit for: {query[:50]}...")
            return [SearchResult(**item) for item in cached_data]

        start_time = datetime.now()

        # Publish start signal
        tool_call_started.send(
            "searchtool", tool_name=tool_name, query=query, start_time=start_time
        )

        task = SearchTask(
            task_id=f"{tool_name}_{time.time():.6f}",
            query=query,
            limit=limit,
        )

        try:
            # Execute with rate limiting and circuit breaker
            result = await self._queue.execute(task, self._execute_search_task)

            # Cache successful results
            if result:
                cache.set(tool_name, query, limit, [r.model_dump() for r in result])

            self._emit_end_signal(tool_name, query, start_time, True, len(result))
            return result

        except CircuitBreakerOpen:
            # Try to return cached result even if circuit is open
            cached_data = cache.get(tool_name, query, limit)
            if cached_data is not None:
                logger.info(
                    f"[{tool_name}] Circuit open, using cached result for: {query[:50]}..."
                )
                self._emit_end_signal(
                    tool_name,
                    query,
                    start_time,
                    True,
                    len(cached_data),
                    "CircuitBreakerOpen_CacheHit",
                )
                return [SearchResult(**item) for item in cached_data]

            logger.warning(f"[{tool_name}] Circuit breaker is OPEN - failing fast")
            self._emit_end_signal(
                tool_name, query, start_time, False, 0, "CircuitBreakerOpen"
            )
            return []

        except asyncio.CancelledError:
            logger.info(f"[{tool_name}] Search cancelled: {query}")
            self._emit_end_signal(tool_name, query, start_time, False, 0, "Cancelled")
            raise

        except Exception as e:
            logger.error(f"[{tool_name}] Search failed: {e}")
            self._emit_end_signal(
                tool_name, query, start_time, False, 0, e.__class__.__name__
            )
            return []

    def _emit_end_signal(
        self,
        tool_name: str,
        query: str,
        start_time: datetime,
        success: bool,
        result_count: int,
        error_type: str = None,
    ):
        """Emit tool call end signal."""
        end_time = datetime.now()
        duration_ms = (end_time - start_time).total_seconds() * 1000

        tool_call_ended.send(
            "searchtool",
            tool_name=tool_name,
            query=query,
            end_time=end_time,
            duration_ms=duration_ms,
            success=success,
            result_count=result_count,
            error_type=error_type,
        )

    async def _execute_search_task(self, task: SearchTask) -> List[SearchResult]:
        """
        Execute the actual search with retry logic.
        This is called by the queue after rate limiting.
        """
        return await self._asearch_with_retry(task)

    async def _asearch_with_retry(self, task: SearchTask) -> List[SearchResult]:
        """
        Execute search with exponential backoff for transient failures.
        Circuit breaker handles persistent failures.
        """
        max_retries = task.max_retries
        base_backoff = 1.0

        for attempt in range(max_retries + 1):
            try:
                return await self._perform_asearch(task.query, task.limit)

            except asyncio.CancelledError:
                logger.info(
                    f"[{self.__class__.__name__}] Task cancelled. Exiting retry loop."
                )
                raise

            except httpx.HTTPStatusError as e:
                # Handle 429 Too Many Requests specifically
                if e.response.status_code == 429 and attempt < max_retries:
                    retry_after = e.response.headers.get("Retry-After")
                    if retry_after:
                        try:
                            backoff_duration = float(retry_after) + 1.0
                        except ValueError:
                            backoff_duration = (
                                base_backoff * (2**attempt)
                            ) + random.uniform(0, 1)
                    else:
                        backoff_duration = (
                            base_backoff * (2**attempt)
                        ) + random.uniform(0, 1)

                    logger.warning(
                        f"[{self.__class__.__name__}] 429 Too Many Requests. "
                        f"Retrying in {backoff_duration:.2f}s... (attempt {attempt + 1}/{max_retries})"
                    )
                    # Notify circuit breaker of the failure even though we're retrying
                    # This ensures the circuit opens when service is consistently rate-limiting
                    self._queue.circuit_breaker.record_failure()
                    await asyncio.sleep(backoff_duration)
                    continue
                else:
                    # Don't retry other HTTP errors or if exhausted
                    raise

            except Exception as e:
                if attempt < max_retries:
                    backoff_duration = (base_backoff * (2**attempt)) + random.uniform(
                        0, 1
                    )
                    logger.warning(
                        f"[{self.__class__.__name__}] Error: {str(e)}. "
                        f"Retrying in {backoff_duration:.2f}s... (attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(backoff_duration)
                    continue
                else:
                    raise

        return []

    async def _perform_asearch(self, query: str, limit: int) -> List[SearchResult]:
        """
        Implement asynchronous search logic.
        Subclasses should override this method.
        """
        raise NotImplementedError

    def get_stats(self) -> Dict[str, Any]:
        """Get current queue and circuit breaker stats for monitoring."""
        return self._queue.get_stats()


class ArxivSearch(SearchTool):
    """Tool to search ArXiv for papers."""

    token_bucket_rate = TOKEN_BUCKET_RATE_ARXIV

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

    token_bucket_rate = TOKEN_BUCKET_RATE_SCHOLAR

    async def _perform_asearch(self, query: str, limit: int) -> List[SearchResult]:
        """Async wrapper for synchronous scholarly search with cancellation support."""
        return await run_in_executor_cancellable(
            self._perform_search_sync, query, limit
        )

    def _perform_search_sync(
        self, query: str, limit: int = SCHOLAR_SEARCH_LIMIT
    ) -> List[SearchResult]:
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


class SemanticScholarSearch(SearchTool):
    """Tool to search Semantic Scholar."""

    token_bucket_rate = TOKEN_BUCKET_RATE_SEMANTIC_SCHOLAR

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

    token_bucket_rate = TOKEN_BUCKET_RATE_OPENREVIEW

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

    token_bucket_rate = TOKEN_BUCKET_RATE_OPENALEX

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

    token_bucket_rate = TOKEN_BUCKET_RATE_DUCKDUCKGO

    async def _perform_asearch(self, query: str, limit: int) -> List[SearchResult]:
        """Async wrapper for synchronous DuckDuckGo search with cancellation support."""
        return await run_in_executor_cancellable(
            self._perform_search_sync, query, limit
        )

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

            # Add timeout control per source to avoid slow sources blocking
            async def search_with_timeout(tool=tool, query=query, limit=limit):
                return await asyncio.wait_for(
                    tool.asearch(query, limit=limit),
                    timeout=8.0,  # 8 second timeout per source
                )

            tasks.append(asyncio.create_task(search_with_timeout()))

        results_list: List[Union[List[SearchResult], Exception]] = await asyncio.gather(
            *tasks, return_exceptions=True
        )

        final_results: List[SearchResult] = []
        failed_sources: List[str] = []

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
                # Empty result (not an error, but no data found)
                failed_sources.append(source_name)

        # Simple deduplication by title (normalized)
        seen_titles = set()
        unique_results: List[SearchResult] = []
        for item in final_results:
            title_norm = item.title.lower().strip()
            if title_norm and title_norm not in seen_titles:
                seen_titles.add(title_norm)
                unique_results.append(prune_search_result(item))

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


def prune_search_result(item: SearchResult) -> SearchResult:
    """Prune result attributes to limit context length."""
    if len(item.title) > 150:
        item.title = item.title[:150] + "..."
    if len(item.abstract) > 300:
        item.abstract = item.abstract[:300] + "..."
    if len(item.authors) > 10:
        item.authors = item.authors[:10]
        item.authors.append("et al.")
    return item


class LocalDBSearch(SearchTool):
    """Local ParadeDB BM25 search for ValiRef Agent."""

    token_bucket_rate = 20.0  # Local database can support higher QPS

    def __init__(self):
        super().__init__()
        self.db_config = {
            "host": DB_HOST,
            "port": DB_PORT,
            "user": DB_USER,
            "password": DB_PASSWORD,
            "database": DB_NAME,
        }
        self._pool: Optional[asyncpg.Pool] = None

    async def _get_pool(self) -> asyncpg.Pool:
        """Get or create connection pool."""
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                host=self.db_config["host"],
                port=self.db_config["port"],
                user=self.db_config["user"],
                password=self.db_config["password"],
                database=self.db_config["database"],
                min_size=2,
                max_size=10,
            )
        return self._pool

    async def _perform_asearch(self, query: str, limit: int = 5) -> List[SearchResult]:
        """Search local ParadeDB using BM25."""
        pool = await self._get_pool()

        try:
            async with pool.acquire() as conn:
                # Escape the query for ParadeDB: wrap in double quotes to treat as phrase
                # This prevents special characters like ':' from being interpreted as field operators
                escaped_query = f'"{query.replace("\"", "\\\"")}"'

                # Use ParadeDB BM25 search with @@@ operator
                # Search in title and abstract fields
                # Note: Schema uses 'year' instead of 'published_date', 'journal_ref' for arxiv date
                sql = """
                    SELECT
                        id,
                        title,
                        authors,
                        year,
                        venue,
                        source,
                        abstract,
                        journal_ref,
                        doi,
                        paradedb.score(id) as rank
                    FROM papers
                    WHERE (title || ' ' || COALESCE(abstract, '')) @@@ $1
                    ORDER BY rank DESC
                    LIMIT $2
                """

                rows = await conn.fetch(sql, escaped_query, limit)

                results = []
                for row in rows:
                    # Parse authors (stored as array in PostgreSQL)
                    authors = row["authors"] or []
                    if isinstance(authors, str):
                        try:
                            authors = json.loads(authors)
                        except json.JSONDecodeError:
                            authors = [authors]

                    # Build URL based on source
                    source = row["source"] or "unknown"
                    if source == "arxiv":
                        url = f"https://arxiv.org/abs/{row['id']}"
                        # For arxiv, year is typically the publication year
                        published_date = str(row["year"]) if row["year"] else "N/A"
                    elif source == "dblp":
                        url = f"https://dblp.org/rec/{row['id']}.html"
                        published_date = str(row["year"]) if row["year"] else "N/A"
                    else:
                        url = row["doi"] or f"https://arxiv.org/abs/{row['id']}"
                        published_date = str(row["year"]) if row["year"] else "N/A"

                    results.append(
                        SearchResult(
                            title=row["title"],
                            authors=authors if isinstance(authors, list) else [],
                            published_date=published_date,
                            venue=row["venue"] or row["journal_ref"] or "N/A",
                            abstract=row["abstract"] or "N/A",
                            url=url,
                            source=f"local_db_{source}",
                        )
                    )

                return results

        except Exception as e:
            logger.error(f"[LocalDBSearch] Database query failed: {e}")
            raise


class LocalAggregateSearch:
    """
    Local aggregate search that only queries local ParadeDB.
    """

    def __init__(self):
        self.tool = LocalDBSearch()

    async def asearch(
        self, query: str, sources: List[str] = None, limit: int = 5
    ) -> List[Dict]:
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

    async def asearch(
        self, query: str, sources: List[str] = None, limit: int = 5
    ) -> List[Dict]:
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

        tasks: List[asyncio.Task[List[SearchResult]]] = []
        for source in valid_sources:
            tool = self.tools[source]

            async def search_with_timeout(tool=tool, query=query, limit=limit):
                return await asyncio.wait_for(
                    tool.asearch(query, limit=limit), timeout=8.0
                )

            tasks.append(asyncio.create_task(search_with_timeout()))

        results_list: List[Union[List[SearchResult], Exception]] = await asyncio.gather(
            *tasks, return_exceptions=True
        )

        final_results: List[SearchResult] = []
        failed_sources: List[str] = []

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
        unique_results: List[SearchResult] = []
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


class AggregateSearchFactory:
    """Search aggregator factory, supports local and online modes."""

    @staticmethod
    def create(mode: str = "local"):
        """
        Create search aggregator.

        Args:
            mode: "local" or "online"

        Returns:
            LocalAggregateSearch or OnlineAggregateSearch instance
        """
        if mode == "local":
            return LocalAggregateSearch()
        elif mode == "online":
            return OnlineAggregateSearch()
        else:
            raise ValueError(f"Unknown search mode: {mode}")
