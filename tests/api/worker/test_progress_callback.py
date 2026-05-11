"""Tests for WorkerProgressCallback and consumer integration"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


class TestWorkerProgressCallback:
    """Test WorkerProgressCallback publishes progress updates to RabbitMQ"""

    @pytest.fixture
    def mock_task_store(self):
        """Mock TaskStore for testing"""
        store = MagicMock()
        store.update_progress = AsyncMock()
        return store

    @pytest.fixture
    def mock_message_queue(self):
        """Mock MessageQueue with channel for testing"""
        queue = MagicMock()
        queue.channel = MagicMock()  # Channel exists
        queue.publish_progress_update = AsyncMock()
        return queue

    @pytest.fixture
    def mock_message_queue_no_channel(self):
        """Mock MessageQueue without channel"""
        queue = MagicMock()
        queue.channel = None  # No channel
        return queue

    @pytest.fixture
    def progress_callback(self, mock_task_store, mock_message_queue):
        """Create WorkerProgressCallback with mocked dependencies"""
        from src.api.worker.progress_callback import WorkerProgressCallback
        return WorkerProgressCallback(
            task_store=mock_task_store,
            task_id="test-task-123",
            queue=mock_message_queue
        )

    @pytest.mark.asyncio
    async def test_update_progress_publishes_to_mq(self, progress_callback, mock_task_store, mock_message_queue):
        """Test that _update_progress publishes to MessageQueue when channel exists"""
        # Set some state
        progress_callback.stage = "validation"
        progress_callback.processed = 5
        progress_callback.total = 10
        progress_callback.current_title = "Test Paper Title"

        await progress_callback._update_progress()

        # Verify task_store.update_progress was called
        mock_task_store.update_progress.assert_called_once_with(
            task_id="test-task-123",
            stage="validation",
            processed=5,
            total=10,
            current_title="Test Paper Title"
        )

        # Verify publish_progress_update was called with correct args
        mock_message_queue.publish_progress_update.assert_called_once()
        call_args = mock_message_queue.publish_progress_update.call_args[1]
        assert call_args["task_id"] == "test-task-123"
        assert call_args["stage"] == "validation"
        assert call_args["processed"] == 5
        assert call_args["total"] == 10
        assert call_args["current_title"] == "Test Paper Title"
        assert call_args["status"] == "validation"

    @pytest.mark.asyncio
    async def test_update_progress_skips_mq_when_no_channel(self, mock_task_store, mock_message_queue_no_channel):
        """Test that _update_progress skips MQ publish when channel is None"""
        from src.api.worker.progress_callback import WorkerProgressCallback

        callback = WorkerProgressCallback(
            task_store=mock_task_store,
            task_id="test-task-456",
            queue=mock_message_queue_no_channel
        )

        await callback._update_progress()

        # Verify task_store.update_progress was still called
        mock_task_store.update_progress.assert_called_once()

        # Verify publish_progress_update was NOT called (no channel)
        assert not hasattr(mock_message_queue_no_channel, 'publish_progress_update') or \
               not mock_message_queue_no_channel.publish_progress_update.called

    @pytest.mark.asyncio
    async def test_update_progress_skips_mq_when_queue_none(self, mock_task_store):
        """Test that _update_progress skips MQ publish when queue is None"""
        from src.api.worker.progress_callback import WorkerProgressCallback

        callback = WorkerProgressCallback(
            task_store=mock_task_store,
            task_id="test-task-789",
            queue=None
        )

        await callback._update_progress()

        # Verify task_store.update_progress was still called
        mock_task_store.update_progress.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_extraction_end_updates_stage(self, progress_callback, mock_task_store, mock_message_queue):
        """Test on_extraction_end sets stage to validation and updates total"""
        # Mock references as simple dicts with title
        references = [
            {"title": "Paper 1"},
            {"title": "Paper 2"},
        ]

        await progress_callback.on_extraction_end(references)

        assert progress_callback.stage == "validation"
        assert progress_callback.total == 2

        # Verify progress was updated
        mock_task_store.update_progress.assert_called()
        mock_message_queue.publish_progress_update.assert_called()

    @pytest.mark.asyncio
    async def test_on_validation_start_sets_stage(self, progress_callback, mock_task_store, mock_message_queue):
        """Test on_validation_start sets stage and total"""
        await progress_callback.on_validation_start(total_references=20)

        assert progress_callback.stage == "validation"
        assert progress_callback.total == 20

        mock_task_store.update_progress.assert_called()
        mock_message_queue.publish_progress_update.assert_called()

    @pytest.mark.asyncio
    async def test_on_reference_validation_start_throttles_updates(self, progress_callback, mock_task_store, mock_message_queue):
        """Test that reference validation updates are throttled (every 5 refs)"""
        # Mock paper as simple object with title attribute
        class MockPaper:
            def __init__(self, title):
                self.title = title

        paper = MockPaper(title="Test Paper")

        # Call for index 0 (should update - 0 % 5 == 0)
        await progress_callback.on_reference_validation_start(paper, index=0, total=20)
        call_count_after_0 = mock_message_queue.publish_progress_update.call_count

        # Call for index 1-4 (should NOT update - none are 0, 5, 10, 15...)
        for i in range(1, 5):
            await progress_callback.on_reference_validation_start(paper, index=i, total=20)
        call_count_after_4 = mock_message_queue.publish_progress_update.call_count

        # Call for index 5 (should update - 5 % 5 == 0)
        await progress_callback.on_reference_validation_start(paper, index=5, total=20)
        call_count_after_5 = mock_message_queue.publish_progress_update.call_count

        # Call for last index (should update - index == total - 1)
        await progress_callback.on_reference_validation_start(paper, index=19, total=20)
        call_count_after_last = mock_message_queue.publish_progress_update.call_count

        # Verify throttling: index 0, 5, and 19 should trigger updates
        assert call_count_after_0 == 1
        assert call_count_after_4 == 1  # No new calls from indices 1-4
        assert call_count_after_5 == 2  # One new call at index 5
        assert call_count_after_last == 3  # One new call at index 19

    @pytest.mark.asyncio
    async def test_on_pipeline_end_sets_completed_status(self, progress_callback, mock_task_store, mock_message_queue):
        """Test on_pipeline_end sets status to completed"""
        await progress_callback.on_pipeline_end({"results": []})

        assert progress_callback.stage == "completed"

        # Verify final update was published with completed status
        mock_message_queue.publish_progress_update.assert_called_once()
        call_args = mock_message_queue.publish_progress_update.call_args[1]
        assert call_args["status"] == "completed"

    @pytest.mark.asyncio
    async def test_mq_publish_failure_is_ignored(self, progress_callback, mock_task_store, mock_message_queue):
        """Test that MQ publish failures are logged but don't break progress updates"""
        # Make publish raise an exception
        mock_message_queue.publish_progress_update.side_effect = Exception("MQ connection lost")

        # Should not raise
        await progress_callback._update_progress()

        # Verify task_store was still updated
        mock_task_store.update_progress.assert_called_once()

