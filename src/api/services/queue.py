import aio_pika
import json
from typing import Callable
from datetime import datetime
from ...core.config import (
    RABBITMQ_URL, RABBITMQ_QUEUE_NAME,
    RABBITMQ_DLQ_NAME, RABBITMQ_DLX_NAME,
    RABBITMQ_MESSAGE_TTL
)


class MessageQueue:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.queue = None
        self.dlq = None
        self.dlx = None
        self.retry_exchange = None
        self.retry_queue = None

    async def connect(self):
        self.connection = await aio_pika.connect_robust(RABBITMQ_URL)
        self.channel = await self.connection.channel()

        # Dead letter exchange - routes failed messages to retry queue first
        self.dlx = await self.channel.declare_exchange(
            RABBITMQ_DLX_NAME,
            aio_pika.ExchangeType.FANOUT,
            durable=True
        )

        # Retry queue: messages wait here for TTL, then route back to main queue
        self.retry_queue = await self.channel.declare_queue(
            f"{RABBITMQ_QUEUE_NAME}_retry",
            durable=True,
            arguments={
                "x-message-ttl": 5000,  # 5 seconds delay before retry
                "x-dead-letter-exchange": "",  # Use default exchange
                "x-dead-letter-routing-key": RABBITMQ_QUEUE_NAME,  # Route back to main queue
            }
        )
        # Bind retry queue to DLX - failed messages go here first
        await self.retry_queue.bind(self.dlx, routing_key="")

        # DLQ: for permanently failed messages (exceeded max retries)
        self.dlq = await self.channel.declare_queue(
            RABBITMQ_DLQ_NAME,
            durable=True
        )
        # Note: DLQ is NOT bound to DLX directly
        # Messages are sent here manually when max retries exceeded

        self.queue = await self.channel.declare_queue(
            RABBITMQ_QUEUE_NAME,
            durable=True,
            arguments={
                "x-dead-letter-exchange": RABBITMQ_DLX_NAME,  # Failed messages -> DLX -> retry queue
                "x-message-ttl": RABBITMQ_MESSAGE_TTL,
            }
        )

    async def publish_pdf_task(self, task_id: str, filename: str, pdf_path: str, search_mode: str = "local", retry_count: int = 0):
        """Publish task to main queue."""
        message = {
            "task_id": task_id,
            "filename": filename,
            "pdf_path": pdf_path,
            "search_mode": search_mode,
            "retry_count": retry_count,
            "published_at": datetime.now().isoformat(),
        }
        await self.channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(message).encode(),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=RABBITMQ_QUEUE_NAME,
        )

    async def publish_to_dlq(self, task_id: str, filename: str, pdf_path: str, search_mode: str, retry_count: int, error_msg: str):
        """Publish permanently failed message to DLQ."""
        message = {
            "task_id": task_id,
            "filename": filename,
            "pdf_path": pdf_path,
            "search_mode": search_mode,
            "retry_count": retry_count,
            "error_msg": error_msg,
            "failed_at": datetime.now().isoformat(),
        }
        await self.channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(message).encode(),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=RABBITMQ_DLQ_NAME,
        )

    async def consume(self, callback: Callable):
        await self.queue.consume(callback)

    async def close(self):
        if self.connection:
            await self.connection.close()
