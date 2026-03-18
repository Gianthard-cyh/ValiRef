"""Tests for search queue components."""

import asyncio
import time
import pytest

from src.core.search_queue import (
    CircuitBreaker,
    CircuitBreakerOpen,
    TokenBucket,
    ToolRequestQueue,
    SearchTask,
    CircuitState,
)


class TestCircuitBreaker:
    """Tests for CircuitBreaker."""

    def test_initial_state_is_closed(self):
        cb = CircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED
        assert cb.can_execute() is True

    def test_records_failure_and_opens_after_threshold(self):
        cb = CircuitBreaker("test", failure_threshold=3)

        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        assert cb.can_execute() is True

        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.can_execute() is False

    def test_success_resets_failure_count_in_closed_state(self):
        cb = CircuitBreaker("test", failure_threshold=3)

        cb.record_failure()
        cb.record_failure()
        cb.record_success()

        # Failures should be reset
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED

    def test_transitions_to_half_open_after_timeout(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.1)

        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.can_execute() is False

        time.sleep(0.15)

        assert cb.can_execute() is True
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_failure_returns_to_open(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.1)

        cb.record_failure()
        time.sleep(0.15)
        cb.can_execute()  # Enter half-open

        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_half_open_success_closes_circuit(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.1, half_open_max_calls=2)

        cb.record_failure()
        time.sleep(0.15)
        cb.can_execute()  # Enter half-open

        cb.record_success()
        cb.record_success()

        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_call_success(self):
        cb = CircuitBreaker("test")

        async def success_func():
            return "success"

        result = await cb.call(success_func)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_call_failure_records_and_raises(self):
        cb = CircuitBreaker("test", failure_threshold=2)

        async def fail_func():
            raise ValueError("error")

        with pytest.raises(ValueError):
            await cb.call(fail_func)

        assert cb.state == CircuitState.CLOSED  # Not enough failures yet

    @pytest.mark.asyncio
    async def test_call_raises_when_open(self):
        cb = CircuitBreaker("test", failure_threshold=1)

        async def fail_func():
            raise ValueError("error")

        with pytest.raises(ValueError):
            await cb.call(fail_func)

        with pytest.raises(CircuitBreakerOpen):
            await cb.call(lambda: "success")


class TestTokenBucket:
    """Tests for TokenBucket."""

    @pytest.mark.asyncio
    async def test_acquire_no_wait_when_tokens_available(self):
        bucket = TokenBucket(rate=10.0, burst_size=5)

        start = time.monotonic()
        wait_time = await bucket.acquire()
        elapsed = time.monotonic() - start

        assert wait_time < 0.01  # Should be instant
        assert elapsed < 0.01

    @pytest.mark.asyncio
    async def test_acquire_waits_when_bucket_empty(self):
        bucket = TokenBucket(rate=100.0, burst_size=1)

        # First acquire consumes the only token
        await bucket.acquire()

        # Second acquire should wait for token generation
        start = time.monotonic()
        wait_time = await bucket.acquire()
        elapsed = time.monotonic() - start

        assert wait_time > 0.005  # Should have waited
        assert elapsed > 0.005

    @pytest.mark.asyncio
    async def test_bucket_refills_over_time(self):
        bucket = TokenBucket(rate=100.0, burst_size=2)

        # Use all tokens
        await bucket.acquire()
        await bucket.acquire()

        # Wait for refill
        await asyncio.sleep(0.02)

        # Should be able to acquire again without much wait
        start = time.monotonic()
        await bucket.acquire()
        elapsed = time.monotonic() - start

        assert elapsed < 0.05  # Should be quick after refill

    @pytest.mark.asyncio
    async def test_respects_cancellation(self):
        bucket = TokenBucket(rate=1.0, burst_size=1)

        # Empty the bucket
        await bucket.acquire()

        task = asyncio.create_task(bucket.acquire())
        await asyncio.sleep(0.01)  # Let it start waiting
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

    def test_get_stats(self):
        bucket = TokenBucket(rate=10.0, burst_size=5)

        stats = bucket.get_stats()
        assert stats["rate"] == 10.0
        assert stats["burst_size"] == 5
        assert stats["tokens_available"] == 5.0


class TestToolRequestQueue:
    """Tests for ToolRequestQueue."""

    @pytest.mark.asyncio
    async def test_execute_success(self):
        queue = ToolRequestQueue("test", token_bucket_rate=100.0)

        async def execute_fn(task: SearchTask) -> str:
            return f"result for {task.query}"

        task = SearchTask(task_id="1", query="test query", limit=5)
        result = await queue.execute(task, execute_fn)

        assert result == "result for test query"

    @pytest.mark.asyncio
    async def test_execute_propagates_exception(self):
        queue = ToolRequestQueue("test", token_bucket_rate=100.0)

        async def fail_fn(task: SearchTask):
            raise ValueError("execution failed")

        task = SearchTask(task_id="1", query="test", limit=5)

        with pytest.raises(ValueError, match="execution failed"):
            await queue.execute(task, fail_fn)

    @pytest.mark.asyncio
    async def test_execute_respects_cancellation(self):
        queue = ToolRequestQueue("test", token_bucket_rate=0.1)

        async def slow_fn(task: SearchTask):
            await asyncio.sleep(10)
            return "done"

        task = SearchTask(task_id="1", query="test", limit=5)

        async def run():
            return await queue.execute(task, slow_fn)

        task_future = asyncio.create_task(run())
        await asyncio.sleep(0.01)
        task_future.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task_future

    def test_get_stats(self):
        queue = ToolRequestQueue(
            "my_tool",
            token_bucket_rate=10.0,
            token_bucket_burst=5,
        )

        stats = queue.get_stats()
        assert stats["tool_name"] == "my_tool"
        assert stats["active_tasks"] == 0
        assert stats["circuit_state"] == "CLOSED"
        assert stats["rate"] == 10.0
        assert stats["burst_size"] == 5


class TestSearchTask:
    """Tests for SearchTask."""

    def test_auto_generates_task_id(self):
        task = SearchTask(task_id="", query="test", limit=5)
        assert task.task_id
        assert isinstance(task.task_id, str)

    def test_preserves_provided_task_id(self):
        task = SearchTask(task_id="my-id", query="test", limit=5)
        assert task.task_id == "my-id"
