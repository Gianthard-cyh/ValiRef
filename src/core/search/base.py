import asyncio
import random
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Callable, List, Optional, TypeVar

from pydantic import BaseModel, Field

from ..config import (
    CIRCUIT_BREAKER_FAILURE_THRESHOLD,
    CIRCUIT_BREAKER_HALF_OPEN_CALLS,
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT,
    TOKEN_BUCKET_BURST_SIZE,
)
from ..exceptions import SearchError
from ..logger import logger
from ..search_cache import get_cache
from ..search_queue import CircuitBreakerOpen, SearchTask, ToolRequestQueue
from ..tool_monitor import tool_call_ended, tool_call_started


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

    def search(self, query: str, limit: int = 5) -> List[dict]:
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
            logger.info("Cache hit", tool_name=tool_name, query=query[:50])
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
                    "Circuit open, using cached result", tool_name=tool_name, query=query[:50]
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

            logger.warning("Circuit breaker is OPEN - failing fast", tool_name=tool_name)
            self._emit_end_signal(
                tool_name, query, start_time, False, 0, "CircuitBreakerOpen"
            )
            return []

        except asyncio.CancelledError:
            logger.info("Search cancelled", tool_name=tool_name, query=query)
            self._emit_end_signal(tool_name, query, start_time, False, 0, "Cancelled")
            raise

        except Exception as e:
            logger.error("Search failed", tool_name=tool_name, error=str(e))
            self._emit_end_signal(
                tool_name, query, start_time, False, 0, e.__class__.__name__
            )
            raise SearchError(f"Search failed for '{query}': {e}") from e

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
        import httpx

        max_retries = task.max_retries
        base_backoff = 1.0

        for attempt in range(max_retries + 1):
            try:
                return await self._perform_asearch(task.query, task.limit)

            except asyncio.CancelledError:
                logger.info(
                    "Task cancelled. Exiting retry loop.", tool_name=self.__class__.__name__
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
                        "429 Too Many Requests. Retrying...",
                        tool_name=self.__class__.__name__,
                        backoff_duration=round(backoff_duration, 2),
                        attempt=attempt + 1,
                        max_retries=max_retries,
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
                        "Search error. Retrying...",
                        tool_name=self.__class__.__name__,
                        error=str(e),
                        backoff_duration=round(backoff_duration, 2),
                        attempt=attempt + 1,
                        max_retries=max_retries,
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

    def get_stats(self) -> dict[str, Any]:
        """Get current queue and circuit breaker stats for monitoring."""
        return self._queue.get_stats()
