"""Unit tests for ValiRef API services and endpoints"""

import pytest
import json
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime


class TestPDFStorage:
    """Test PDF file storage service"""

    @pytest.fixture
    def temp_storage(self, tmp_path):
        from src.api.services.pdf_storage import PDFStorage
        return PDFStorage(storage_path=str(tmp_path))

    @pytest.mark.asyncio
    async def test_save_pdf_file(self, temp_storage, tmp_path):
        """测试PDF文件保存和路径生成"""
        task_id = "abc12345-6789"
        filename = "test_paper.pdf"
        content = b"PDF content bytes"

        pdf_path = await temp_storage.save(task_id, filename, content)

        assert pdf_path is not None
        assert Path(pdf_path).exists()
        assert Path(pdf_path).read_bytes() == content
        # 验证路径结构: tmp_path/ab/c1/abc12345-6789_test_paper.pdf
        assert task_id[:2] in pdf_path
        assert task_id[2:4] in pdf_path
        assert "test_paper.pdf" in pdf_path

    @pytest.mark.asyncio
    async def test_get_existing_pdf(self, temp_storage):
        """测试获取已存在的PDF文件路径"""
        task_id = "test123"
        filename = "paper.pdf"
        content = b"PDF data"

        saved_path = await temp_storage.save(task_id, filename, content)
        retrieved_path = temp_storage.get(task_id, filename)

        assert retrieved_path == saved_path

    def test_get_nonexistent_pdf(self, temp_storage):
        """测试获取PDF文件路径（不检查是否存在）"""
        result = temp_storage.get("nonexistent", "file.pdf")
        # get() 现在返回路径而不检查存在性
        assert result is not None
        assert "nonexistent" in result
        assert result.endswith("file.pdf")

    @pytest.mark.asyncio
    async def test_delete_pdf(self, temp_storage):
        """测试删除PDF文件"""
        task_id = "delete_test"
        filename = "delete.pdf"
        content = b"delete me"

        await temp_storage.save(task_id, filename, content)
        # 文件存在时get返回路径
        assert temp_storage.get(task_id, filename) is not None

        deleted = temp_storage.delete(task_id, filename)
        assert deleted is True
        # 删除后get仍返回路径（不检查存在性）
        assert temp_storage.get(task_id, filename) is not None
        # 但文件实际已删除
        assert not Path(temp_storage.get(task_id, filename)).exists()

    def test_delete_nonexistent_pdf(self, temp_storage):
        """测试删除不存在的PDF文件"""
        result = temp_storage.delete("nonexistent", "file.pdf")
        assert result is False

    @pytest.mark.asyncio
    async def test_filename_sanitization(self, temp_storage, tmp_path):
        """测试文件名清理（只保留安全字符）"""
        task_id = "sanitize_test"
        # 包含不安全字符的文件名
        filename = "paper<script>alert(1)</script>.pdf"
        content = b"content"

        pdf_path = await temp_storage.save(task_id, filename, content)

        # 文件名应该被清理
        assert "<script>" not in pdf_path
        assert pdf_path.endswith(".pdf")


class TestTaskStore:
    """Test task status storage"""

    @pytest.fixture
    def task_store(self):
        from src.api.services.task_store import TaskStore
        store = TaskStore()
        # Mock the pool
        store.pool = AsyncMock()
        return store

    @pytest.mark.asyncio
    async def test_create_task(self, task_store):
        """测试创建新任务"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = {
            "task_id": "task-123",
            "status": "pending",
            "filename": "test.pdf",
            "created_at": datetime.now()
        }

        # Properly mock the async context manager
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        task_store.pool.acquire = MagicMock(return_value=mock_cm)

        result = await task_store.create_task(
            task_id="task-123",
            filename="test.pdf",
            pdf_path="/tmp/test.pdf",
            request_data={"search_mode": "local"}
        )

        assert result["task_id"] == "task-123"
        assert result["status"] == "pending"
        mock_conn.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_task(self, task_store):
        """测试查询任务"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = {
            "task_id": "task-456",
            "status": "processing",
            "filename": "paper.pdf",
            "result": {"total_references": 10},
            "created_at": datetime.now()
        }

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        task_store.pool.acquire = MagicMock(return_value=mock_cm)

        result = await task_store.get_task("task-456")

        assert result is not None
        assert result["status"] == "processing"

    @pytest.mark.asyncio
    async def test_get_nonexistent_task(self, task_store):
        """测试查询不存在的任务"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = None

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        task_store.pool.acquire = MagicMock(return_value=mock_cm)

        result = await task_store.get_task("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_update_status_to_completed(self, task_store):
        """测试更新任务状态为完成"""
        mock_conn = AsyncMock()

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        task_store.pool.acquire = MagicMock(return_value=mock_cm)

        await task_store.update_status(
            task_id="task-789",
            status="completed",
            result={"total_references": 5},
            progress_processed=5,
            progress_total=5
        )

        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args[0]
        assert "completed" in str(call_args)

    @pytest.mark.asyncio
    async def test_increment_retry(self, task_store):
        """测试增加重试次数"""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = {"retry_count": 2}

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        task_store.pool.acquire = MagicMock(return_value=mock_cm)

        retry_count = await task_store.increment_retry("task-001", "Error message")

        assert retry_count == 2

    @pytest.mark.asyncio
    async def test_get_status_stats(self, task_store):
        """测试按状态统计"""
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = [
            {"status": "pending", "count": 5},
            {"status": "completed", "count": 10},
            {"status": "failed", "count": 2}
        ]

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        task_store.pool.acquire = MagicMock(return_value=mock_cm)

        stats = await task_store.get_status_stats()

        assert stats["pending"] == 5
        assert stats["completed"] == 10
        assert stats["failed"] == 2


class TestMessageQueue:
    """Test RabbitMQ message queue"""

    @pytest.fixture
    def message_queue(self):
        from src.api.services.queue import MessageQueue
        queue = MessageQueue()
        queue.connection = AsyncMock()
        queue.channel = AsyncMock()
        queue.channel.default_exchange = AsyncMock()
        return queue

    @pytest.mark.asyncio
    async def test_publish_pdf_task(self, message_queue):
        """测试发布PDF任务消息"""
        await message_queue.publish_pdf_task(
            task_id="task-001",
            filename="paper.pdf",
            pdf_path="/tmp/paper.pdf",
            search_mode="local"
        )

        message_queue.channel.default_exchange.publish.assert_called_once()
        call_args = message_queue.channel.default_exchange.publish.call_args
        message = call_args[0][0]
        assert message.content_type == "application/json"
        assert message.delivery_mode.value == 2  # PERSISTENT

    @pytest.mark.asyncio
    async def test_publish_to_dlq(self, message_queue):
        """测试发布消息到DLQ"""
        message_queue.channel.default_exchange = AsyncMock()

        await message_queue.publish_to_dlq(
            task_id="task-003",
            filename="paper.pdf",
            pdf_path="/tmp/paper.pdf",
            search_mode="local",
            retry_count=3,
            error_msg="Max retries exceeded"
        )

        message_queue.channel.default_exchange.publish.assert_called_once()
        call_args = message_queue.channel.default_exchange.publish.call_args
        message = call_args[0][0]
        assert message.content_type == "application/json"
        assert message.delivery_mode.value == 2  # PERSISTENT


class TestAPIRoutes:
    """Test FastAPI routes"""

    @pytest.fixture
    def mock_app_state(self):
        """Create mock app state for dependency injection"""
        state = Mock()
        state.task_store = AsyncMock()
        state.queue = AsyncMock()
        return state

    def test_submit_pdf_success(self, mock_app_state):
        """测试PDF上传流程，task_id生成，文件存储"""
        from fastapi.testclient import TestClient
        from src.api.main import app

        # Setup mocks
        mock_app_state.task_store.create_task.return_value = {
            "task_id": "test-task-id",
            "status": "pending",
            "filename": "test.pdf"
        }

        # Create test client with mocked dependencies
        with patch.object(app, 'state', mock_app_state):
            from fastapi.testclient import TestClient
            client = TestClient(app)

            response = client.post(
                "/validation/submit",
                files={"file": ("test.pdf", b"PDF content", "application/pdf")},
                data={"search_mode": "local"}
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"
        assert data["filename"] == "test.pdf"
        assert "task_id" in data
        mock_app_state.queue.publish_pdf_task.assert_called_once()

    def test_submit_pdf_invalid_file_type(self, mock_app_state):
        """测试上传非PDF文件返回错误"""
        from src.api.main import app

        with patch.object(app, 'state', mock_app_state):
            from fastapi.testclient import TestClient
            client = TestClient(app)

            response = client.post(
                "/validation/submit",
                files={"file": ("test.txt", b"Text content", "text/plain")},
                data={"search_mode": "local"}
            )

        assert response.status_code == 400
        assert "Only PDF files are allowed" in response.json()["detail"]

    def test_get_result_success(self, mock_app_state):
        """测试查询PDF验证结果"""
        from src.api.main import app
        from datetime import datetime

        mock_app_state.task_store.get_task.return_value = {
            "task_id": "task-123",
            "status": "completed",
            "filename": "paper.pdf",
            "result": {
                "total_references": 10,
                "validated_count": 10,
                "real_count": 8,
                "hallucination_count": 2,
                "references": []
            },
            "created_at": datetime.now(),
            "completed_at": datetime.now()
        }

        with patch.object(app, 'state', mock_app_state):
            from fastapi.testclient import TestClient
            client = TestClient(app)

            response = client.get("/validation/result/task-123")

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "task-123"
        assert data["status"] == "completed"
        assert data["total_references"] == 10

    def test_get_result_with_error_code(self, mock_app_state):
        """测试查询失败任务返回 error_code"""
        from src.api.main import app
        from datetime import datetime

        mock_app_state.task_store.get_task.return_value = {
            "task_id": "task-124",
            "status": "failed_permanently",
            "filename": "corrupted.pdf",
            "result": None,
            "error_code": "pdf_corrupted",
            "error_message": "Failed to open PDF file: Invalid PDF header",
            "created_at": datetime.now(),
            "completed_at": datetime.now()
        }

        with patch.object(app, 'state', mock_app_state):
            from fastapi.testclient import TestClient
            client = TestClient(app)

            response = client.get("/validation/result/task-124")

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "task-124"
        assert data["status"] == "failed_permanently"
        assert data["error_code"] == "pdf_corrupted"
        assert "Invalid PDF" in data["error_message"]

    def test_get_result_not_found(self, mock_app_state):
        """测试查询不存在的任务返回404"""
        from src.api.main import app

        mock_app_state.task_store.get_task.return_value = None

        with patch.object(app, 'state', mock_app_state):
            from fastapi.testclient import TestClient
            client = TestClient(app)

            response = client.get("/validation/result/nonexistent")

        assert response.status_code == 404

    def test_get_status_with_progress(self, mock_app_state):
        """测试查询任务状态包含进度信息"""
        from src.api.main import app
        from datetime import datetime

        mock_app_state.task_store.get_task.return_value = {
            "task_id": "task-456",
            "status": "processing",
            "filename": "paper.pdf",
            "progress_processed": 5,
            "progress_total": 10,
            "created_at": datetime.now()
        }

        with patch.object(app, 'state', mock_app_state):
            from fastapi.testclient import TestClient
            client = TestClient(app)

            response = client.get("/validation/status/task-456")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processing"
        assert data["progress"]["processed"] == 5
        assert data["progress"]["total"] == 10

    def test_get_status_with_error_code(self, mock_app_state):
        """测试查询任务状态包含 error_code"""
        from src.api.main import app
        from datetime import datetime

        mock_app_state.task_store.get_task.return_value = {
            "task_id": "task-457",
            "status": "failed_permanently",
            "filename": "scanned.pdf",
            "error_code": "pdf_no_text",
            "progress_processed": 0,
            "progress_total": 0,
            "created_at": datetime.now()
        }

        with patch.object(app, 'state', mock_app_state):
            from fastapi.testclient import TestClient
            client = TestClient(app)

            response = client.get("/validation/status/task-457")

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "task-457"
        assert data["status"] == "failed_permanently"
        assert data["error_code"] == "pdf_no_text"

    def test_get_stats(self, mock_app_state):
        """测试获取队列统计信息"""
        from src.api.main import app

        mock_app_state.task_store.get_status_stats.return_value = {
            "pending": 10,
            "processing": 5,
            "completed": 85
        }

        with patch.object(app, 'state', mock_app_state):
            from fastapi.testclient import TestClient
            client = TestClient(app)

            response = client.get("/validation/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 100
        assert data["by_status"]["pending"] == 10


class TestPDFValidationWorker:
    """Test RabbitMQ Worker consumer"""

    @pytest.fixture
    def mock_worker(self):
        from src.api.worker.consumer import PDFValidationWorker
        worker = PDFValidationWorker()
        worker.task_store = AsyncMock()
        worker.queue = AsyncMock()
        worker.pipeline = AsyncMock()
        return worker

    @pytest.mark.asyncio
    async def test_process_message_success(self, mock_worker):
        """测试Worker PDF处理流程和结果存储"""
        mock_message = MagicMock()
        mock_message.body = json.dumps({
            "task_id": "task-001",
            "filename": "test.pdf",
            "pdf_path": "/tmp/test.pdf",
            "search_mode": "local",
            "retry_count": 0
        }).encode()

        mock_worker.pipeline.process_pdf.return_value = {
            "references_count": 2,
            "validated_count": 2,
            "duration_seconds": 10.5,
            "results": [
                {
                    "paper": {"title": "Paper 1", "authors": ["Author 1"]},
                    "validation": {"is_hallucination": False, "confidence": 0.9, "reasoning": "Real", "evidence": []}
                },
                {
                    "paper": {"title": "Paper 2", "authors": ["Author 2"]},
                    "validation": {"is_hallucination": True, "hallucination_type": "fabrication", "confidence": 0.8, "reasoning": "Fake", "evidence": []}
                }
            ]
        }

        # Create async context manager mock for message.process()
        mock_process_cm = MagicMock()
        mock_process_cm.__aenter__ = AsyncMock(return_value=None)
        mock_process_cm.__aexit__ = AsyncMock(return_value=None)
        mock_message.process.return_value = mock_process_cm

        await mock_worker.process_message(mock_message)

        mock_worker.task_store.update_status.assert_called()
        # Verify the completed status update was called with results
        calls = mock_worker.task_store.update_status.call_args_list
        assert len(calls) >= 1
        # Check that the last call has "completed" status
        last_call = calls[-1]
        # Access args: (task_id, status, ...)
        args = last_call[0]
        assert args[1] == "completed"

    @pytest.mark.asyncio
    async def test_worker_under_max_retries_raises_for_retry(self, mock_worker):
        """测试Worker在重试次数内抛出异常，让RabbitMQ自动重试"""
        mock_message = MagicMock()
        mock_message.body = json.dumps({
            "task_id": "task-002",
            "filename": "test.pdf",
            "pdf_path": "/tmp/test.pdf",
            "search_mode": "local",
            "retry_count": 0  # 未达到最大重试次数
        }).encode()

        # Simulate pipeline failure
        mock_worker.pipeline.process_pdf.side_effect = Exception("Processing error")

        mock_process_cm = MagicMock()
        mock_process_cm.__aenter__ = AsyncMock(return_value=None)
        mock_process_cm.__aexit__ = AsyncMock(return_value=None)
        mock_message.process.return_value = mock_process_cm

        # process_message raises exception to trigger RabbitMQ retry via DLX
        with pytest.raises(Exception, match="Processing error"):
            await mock_worker.process_message(mock_message)

        # Should update task status to processing then fail
        mock_worker.task_store.update_status.assert_called()
        # Should NOT publish to DLQ (will be retried via RabbitMQ DLX)
        mock_worker.queue.publish_to_dlq.assert_not_called()

    @pytest.mark.asyncio
    async def test_worker_max_retries_exceeded_sends_to_dlq(self, mock_worker):
        """测试超过最大重试次数时发送到DLQ"""
        mock_message = MagicMock()
        mock_message.body = json.dumps({
            "task_id": "task-003",
            "filename": "test.pdf",
            "pdf_path": "/tmp/test.pdf",
            "search_mode": "local",
            "retry_count": 3  # 已达到最大重试次数
        }).encode()

        mock_worker.pipeline.process_pdf.side_effect = Exception("Processing error")

        mock_process_cm = MagicMock()
        mock_process_cm.__aenter__ = AsyncMock(return_value=None)
        mock_process_cm.__aexit__ = AsyncMock(return_value=None)
        mock_message.process.return_value = mock_process_cm

        # process_message should NOT raise - it handles the failure by sending to DLQ
        await mock_worker.process_message(mock_message)

        # Should mark as failed_permanently
        calls = mock_worker.task_store.update_status.call_args_list
        last_call = calls[-1]
        args = last_call[0]
        assert args[1] == "failed_permanently"

        # Should publish to DLQ
        mock_worker.queue.publish_to_dlq.assert_called_once()


class TestHealthEndpoint:
    """Test health check endpoint"""

    def test_health_check(self):
        """测试健康检查端点"""
        from src.api.main import app
        from fastapi.testclient import TestClient
        from unittest.mock import AsyncMock

        # Mock dependencies
        mock_task_store = AsyncMock()
        mock_task_store.get_task.return_value = None
        mock_queue = AsyncMock()
        mock_queue.connection.is_closed = False

        app.state.task_store = mock_task_store
        app.state.queue = mock_queue

        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "valiref-api"
