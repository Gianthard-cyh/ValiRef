import asyncio
import json
import signal
from datetime import datetime

import aio_pika
import asyncpg

from ...core.config import (
    DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME,
    WORKER_PREFETCH_COUNT
)
from ..services.queue import MessageQueue


class MinimalWorker:
    def __init__(self):
        self.db_pool = None
        self.queue = MessageQueue()
        self._shutdown_event = asyncio.Event()
        self._consumer_tag = None
        self._running_tasks = set()

    async def init_db(self):
        print(f"Connecting to PostgreSQL: {DB_HOST}:{DB_PORT}/{DB_NAME}")
        self.db_pool = await asyncpg.create_pool(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            min_size=1,
            max_size=5,
        )
        print("PostgreSQL connected")

    async def update_task_status(self, task_id: str, status: str, result: dict = None):
        async with self.db_pool.acquire() as conn:
            completed_at = None
            if status in ("completed", "failed", "failed_permanently"):
                completed_at = datetime.now()

            await conn.execute(
                """UPDATE pdf_validation_tasks
                   SET status = $2,
                       result = $3,
                       completed_at = COALESCE($4, completed_at),
                       updated_at = CURRENT_TIMESTAMP
                   WHERE task_id = $1""",
                task_id,
                status,
                json.dumps(result) if result else None,
                completed_at
            )

    async def initialize(self):
        await self.init_db()
        await self.queue.connect()
        print("Connected to PostgreSQL and RabbitMQ")

    async def _process_message_wrapper(self, message: aio_pika.IncomingMessage):
        task = asyncio.current_task()
        self._running_tasks.add(task)
        try:
            await self._process_message(message)
        finally:
            self._running_tasks.discard(task)

    async def _process_message(self, message: aio_pika.IncomingMessage):
        async with message.process():
            data = json.loads(message.body.decode())
            task_id = data["task_id"]
            filename = data["filename"]

            print(f"[Task {task_id}] Received: {filename}")

            print(f"[Task {task_id}] Updating status to PROCESSING...")
            await self.update_task_status(task_id, "processing")
            print(f"[Task {task_id}] Status updated to PROCESSING")

            await asyncio.sleep(1)

            print(f"[Task {task_id}] Updating status to COMPLETED...")
            await self.update_task_status(task_id, "completed", result={"test": True})
            print(f"[Task {task_id}] Status updated to COMPLETED - Done!")

    async def _message_callback(self, message: aio_pika.IncomingMessage):
        task = asyncio.create_task(self._process_message_wrapper(message))
        task.add_done_callback(lambda t: t.exception() if t.exception() else None)

    async def run(self):
        await self.initialize()

        def signal_handler():
            print("\nReceived shutdown signal...")
            self._shutdown_event.set()

        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, signal_handler)

        channel = self.queue.channel
        await channel.set_qos(prefetch_count=WORKER_PREFETCH_COUNT)

        self._consumer_tag = await self.queue.queue.consume(self._message_callback)
        print(f"Minimal Worker started (consumer={self._consumer_tag}) - Press Ctrl+C to stop")

        await self._shutdown_event.wait()

        print("\nShutdown requested...")

        if self._consumer_tag:
            print("Cancelling consumer...")
            await self.queue.queue.cancel(self._consumer_tag)

        if self._running_tasks:
            print(f"Waiting for {len(self._running_tasks)} tasks to complete...")
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._running_tasks, return_exceptions=True),
                    timeout=30
                )
            except asyncio.TimeoutError:
                print("Timeout waiting for tasks, forcing shutdown")

        print("Closing RabbitMQ connection...")
        await self.queue.close()

        print("Closing PostgreSQL connection pool...")
        if self.db_pool:
            await self.db_pool.close()

        print("Worker stopped")


if __name__ == "__main__":
    worker = MinimalWorker()
    asyncio.run(worker.run())
