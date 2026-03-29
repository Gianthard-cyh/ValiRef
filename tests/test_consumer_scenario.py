"""模拟 Consumer 场景测试 TaskStore"""
import asyncio
import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_consumer_scenario():
    """模拟 consumer 的调用场景"""
    try:
        from src.api.services.task_store import TaskStore
        from src.api.schemas.api import TaskStatus
        import uuid

        logger.info("=== 模拟 Consumer 场景测试 ===")

        # 1. 创建 TaskStore（不初始化）
        store = TaskStore()
        logger.info(f"TaskStore created, pool={store.pool}")

        # 2. 初始化
        logger.info("Initializing...")
        await store.initialize()
        logger.info(f"Initialized, pool={store.pool}")

        # 3. 创建任务
        task_id = str(uuid.uuid4())
        logger.info(f"Creating task {task_id}...")
        await store.create_task(task_id, "test.pdf", "/tmp/test.pdf", {})

        # 4. 模拟 consumer: 立即更新状态（这是 consumer 第67行的操作）
        logger.info(f"[Consumer] Updating status to PROCESSING...")
        await store.update_status(task_id, TaskStatus.PROCESSING)
        logger.info(f"[Consumer] Status updated!")

        # 5. 验证
        task = await store.get_task(task_id)
        logger.info(f"Task status: {task['status']}")

        # 6. 模拟长时间处理后的更新
        logger.info("[Consumer] Simulating long processing...")
        await asyncio.sleep(2)

        logger.info(f"[Consumer] Updating status to COMPLETED...")
        await store.update_status(task_id, TaskStatus.COMPLETED, result={"test": True})
        logger.info(f"[Consumer] Status updated!")

        logger.info("=== 测试通过！===")
        await store.close()

    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_consumer_scenario())
