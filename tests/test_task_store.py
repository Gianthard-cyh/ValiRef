"""测试 TaskStore 的 update_status 方法是否能正常写入数据库"""
import asyncio
import logging
import sys
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Enable asyncpg debug logging
asyncpg_logger = logging.getLogger('asyncpg')
asyncpg_logger.setLevel(logging.DEBUG)


@pytest.mark.asyncio
async def test_update_status():
    """测试 update_status 方法"""
    try:
        from src.api.services.task_store import TaskStore
        from src.api.schemas.api import TaskStatus
        import uuid

        logger.info("=== Starting TaskStore update_status test ===")

        store = TaskStore()

        # 1. 初始化连接
        logger.info("Step 1: Initializing TaskStore...")
        await store.initialize()
        logger.info("TaskStore initialized successfully")

        # 2. 创建测试任务
        task_id = str(uuid.uuid4())
        filename = "test.pdf"
        pdf_path = "/tmp/test.pdf"
        request_data = {"search_mode": "local"}

        logger.info(f"Step 2: Creating task {task_id}...")
        task = await store.create_task(task_id, filename, pdf_path, request_data)
        logger.info(f"Task created: {task}")

        # 3. 测试 update_status - PROCESSING
        logger.info(f"Step 3: Updating status to PROCESSING...")
        await store.update_status(task_id, TaskStatus.PROCESSING)
        logger.info("Status updated to PROCESSING")

        # 验证
        task_after = await store.get_task(task_id)
        logger.info(f"Task after PROCESSING: status={task_after['status']}")
        assert task_after['status'] == 'processing', f"Expected 'processing', got '{task_after['status']}'"

        # 4. 测试 update_status - COMPLETED with result
        logger.info(f"Step 4: Updating status to COMPLETED with result...")
        result = {
            "total_references": 10,
            "validated_count": 10,
            "real_count": 8,
            "hallucination_count": 2,
            "references": [],
            "duration_seconds": 5.5
        }
        await store.update_status(task_id, TaskStatus.COMPLETED, result=result)
        logger.info("Status updated to COMPLETED")

        # 验证
        task_final = await store.get_task(task_id)
        logger.info(f"Task after COMPLETED: status={task_final['status']}, result={task_final.get('result')}")
        assert task_final['status'] == 'completed', f"Expected 'completed', got '{task_final['status']}'"
        assert task_final['result'] is not None, "Result should not be None"

        logger.info("=== All tests passed! ===")

        # 5. 清理
        await store.close()
        logger.info("TaskStore closed")

    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


@pytest.mark.asyncio
async def test_update_status_with_error_code():
    """测试 update_status 方法支持 error_code"""
    try:
        from src.api.services.task_store import TaskStore
        from src.api.schemas.api import TaskStatus
        from src.core.exceptions import ErrorCode
        import uuid

        logger.info("=== Starting TaskStore error_code test ===")

        store = TaskStore()
        await store.initialize()

        # 创建测试任务
        task_id = str(uuid.uuid4())
        await store.create_task(task_id, "test.pdf", "/tmp/test.pdf", {})

        # 测试带 error_code 的失败状态
        await store.update_status(
            task_id,
            TaskStatus.FAILED_PERMANENTLY,
            error_code=ErrorCode.PDF_CORRUPTED,
            error_message="PDF file is corrupted"
        )

        # 验证
        task = await store.get_task(task_id)
        logger.info(f"Task after FAILED: error_code={task.get('error_code')}, error_message={task.get('error_message')}")
        assert task['status'] == 'failed_permanently'
        assert task['error_code'] == 'pdf_corrupted', f"Expected 'pdf_corrupted', got '{task.get('error_code')}'"
        assert "corrupted" in task['error_message'].lower(), f"Expected error message about corruption, got '{task.get('error_message')}'"

        logger.info("=== error_code test passed! ===")

        await store.close()

    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(test_update_status())
    asyncio.run(test_update_status_with_error_code())
