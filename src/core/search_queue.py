"""
Local message queue system for search tool requests.

Provides:
- Token bucket rate limiting (smooth request flow)
- Circuit breaker pattern (fail-fast for unhealthy tools)
- Async queue buffering with proper cancellation support
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Callable, Optional, Any
import threading

from .logger import logger


@dataclass
class SearchTask:
    """Task object representing a search request."""

    task_id: str
    query: str
    limit: int
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if not self.task_id:
            self.task_id = f"{id(self)}_{time.time():.6f}"


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = auto()  # Normal operation
    OPEN = auto()  # Circuit is open (failing fast)
    HALF_OPEN = auto()  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.

    Prevents cascading failures by stopping requests to a failing service.
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service is failing, reject requests immediately
    - HALF_OPEN: Testing if service recovered
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state (thread-safe)."""
        with self._lock:
            return self._state

    def can_execute(self) -> bool:
        """Check if a request can be executed."""
        with self._lock:
            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                if (
                    self._last_failure_time
                    and (time.time() - self._last_failure_time) >= self.recovery_timeout
                ):
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    logger.info(
                        "Circuit breaker entering HALF_OPEN state", tool_name=self.name
                    )
                    return True
                return False

            if self._state == CircuitState.HALF_OPEN:
                # Allow limited calls in half-open state
                if self._half_open_calls < self.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
                return False

            return True

    def record_success(self):
        """Record a successful execution."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.half_open_max_calls:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
                    self._half_open_calls = 0
                    logger.info("Circuit breaker CLOSED (recovered)", tool_name=self.name)
            else:
                self._failure_count = 0

    def record_failure(self):
        """Record a failed execution."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                # Failure in half-open: go back to open
                self._state = CircuitState.OPEN
                self._half_open_calls = 0
                logger.warning("Circuit breaker OPEN (recovery failed)", tool_name=self.name)
            elif self._failure_count >= self.failure_threshold:
                if self._state != CircuitState.OPEN:
                    self._state = CircuitState.OPEN
                    logger.warning(
                        "Circuit breaker OPEN after failures",
                        tool_name=self.name,
                        failure_threshold=self.failure_threshold,
                    )

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function with circuit breaker protection.

        Args:
            func: The function to execute
            *args, **kwargs: Arguments to pass to the function

        Returns:
            The result of the function call

        Raises:
            CircuitBreakerOpen: If the circuit is open
            Exception: Any exception raised by the function
        """
        if not self.can_execute():
            raise CircuitBreakerOpen(f"[{self.name}] Circuit breaker is OPEN")

        try:
            result = await func(*args, **kwargs)
            self.record_success()
            return result
        except Exception:
            self.record_failure()
            raise


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open."""

    pass


class TokenBucket:
    """
    Token bucket rate limiter.

    Provides smooth rate limiting with support for bursts.
    Uses atomic-like updates without blocking during waits.
    """

    def __init__(
        self,
        rate: float,  # tokens per second
        burst_size: Optional[int] = None,  # maximum bucket size
    ):
        """
        Initialize token bucket.

        Args:
            rate: Number of tokens generated per second
            burst_size: Maximum tokens that can be accumulated (defaults to rate)
        """
        self.rate = rate
        self.burst_size = burst_size or max(1, int(rate))
        self._tokens = float(self.burst_size)
        self._last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> float:
        """
        Acquire tokens from the bucket.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            Time waited for the tokens

        Raises:
            asyncio.CancelledError: If the task is cancelled while waiting
        """
        start_time = time.monotonic()

        while True:
            async with self._lock:
                now = time.monotonic()
                elapsed = now - self._last_update

                # Add tokens based on elapsed time
                self._tokens = min(self.burst_size, self._tokens + elapsed * self.rate)
                self._last_update = now

                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return time.monotonic() - start_time

                # Calculate wait time needed
                tokens_needed = tokens - self._tokens
                wait_time = tokens_needed / self.rate

            # Release lock before sleeping to allow concurrency
            try:
                await asyncio.sleep(wait_time)
            except asyncio.CancelledError:
                # Re-calculate tokens for time actually waited before re-raising
                async with self._lock:
                    actual_elapsed = time.monotonic() - now
                    self._tokens = min(
                        self.burst_size, self._tokens + actual_elapsed * self.rate
                    )
                    self._last_update = time.monotonic()
                raise

    def get_stats(self) -> dict:
        """Get current bucket statistics."""
        return {
            "tokens_available": self._tokens,
            "burst_size": self.burst_size,
            "rate": self.rate,
        }


class ToolRequestQueue:
    """
    Request queue for a search tool.

    Each SearchTool instance has its own queue with:
    - Token bucket rate limiting
    - Circuit breaker protection
    - Proper cancellation handling

    No persistent worker coroutines - requests are processed on-demand.
    """

    def __init__(
        self,
        tool_name: str,
        token_bucket_rate: float,
        token_bucket_burst: Optional[int] = None,
        circuit_failure_threshold: int = 5,
        circuit_recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
    ):
        """
        Initialize the tool request queue.

        Args:
            tool_name: Name of the tool (for logging)
            token_bucket_rate: Rate limit in tokens per second
            token_bucket_burst: Maximum burst size
            circuit_failure_threshold: Failures before opening circuit
            circuit_recovery_timeout: Seconds before attempting recovery
            half_open_max_calls: Successful calls needed to close circuit
        """
        self.tool_name = tool_name
        self.token_bucket = TokenBucket(
            rate=token_bucket_rate, burst_size=token_bucket_burst
        )
        self.circuit_breaker = CircuitBreaker(
            name=tool_name,
            failure_threshold=circuit_failure_threshold,
            recovery_timeout=circuit_recovery_timeout,
            half_open_max_calls=half_open_max_calls,
        )
        self._active_count = 0
        self._lock = asyncio.Lock()

    async def execute(
        self, task: SearchTask, execute_fn: Callable[[SearchTask], Any]
    ) -> Any:
        """
        Execute a task with rate limiting and circuit breaker protection.

        This method processes the task immediately (no persistent worker).

        Args:
            task: The search task to execute
            execute_fn: The actual execution function

        Returns:
            The result from execute_fn

        Raises:
            asyncio.CancelledError: If the task is cancelled
            CircuitBreakerOpen: If the circuit breaker is open
            Exception: Any exception from execute_fn
        """
        async with self._lock:
            self._active_count += 1

        try:
            # 1. Wait for rate limit token (interruptible)
            await self.token_bucket.acquire()

            # 2. Execute with circuit breaker protection
            return await self.circuit_breaker.call(execute_fn, task)

        except asyncio.CancelledError:
            logger.debug("Task cancelled", tool_name=self.tool_name, task_id=task.task_id)
            raise

        finally:
            async with self._lock:
                self._active_count -= 1

    def get_stats(self) -> dict:
        """Get current queue statistics."""
        return {
            "tool_name": self.tool_name,
            "active_tasks": self._active_count,
            "circuit_state": self.circuit_breaker.state.name,
            **self.token_bucket.get_stats(),
        }
