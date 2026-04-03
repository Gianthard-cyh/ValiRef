"""RabbitMQ Consumer with structured logging."""

import asyncio
import json
import signal
import time
import traceback
from pathlib import Path
from typing import Optional

import aio_pika
import structlog

from src.core.logger import set_logger_mode
from ...core.config import (
    RABBITMQ_URL,
    RABBITMQ_QUEUE_NAME,
    RABBITMQ_MAX_RETRIES,
    WORKER_CONCURRENCY,
    WORKER_PREFETCH_COUNT,
)
from ...core.extract import PDFExtractor, TextExtractor
from ...core.pipeline import ValidationPipeline
from ...core.logger import get_logger
from ...core.exceptions import get_error_code
from ..schemas.api import TaskStatus
from ..services.queue import MessageQueue
from ..services.task_store import TaskStore
from ..services.metrics import (
    tasks_completed,
    tasks_failed,
    tasks_active,
    task_duration_seconds,
)
from prometheus_client import start_http_server

# Configure logging for backend (JSON format)
set_logger_mode("json")
logger = get_logger(__name__)


class PDFValidationWorker:
    def __init__(self):
        self.task_store = TaskStore()
        self.queue = MessageQueue()
        self.semaphore = asyncio.Semaphore(WORKER_CONCURRENCY)
        self.pipeline: ValidationPipeline = None
        self._shutdown_event = asyncio.Event()

    async def initialize(self):
        from ...cli import create_detector, create_llm

        logger.info("Initializing Worker...")

        llm = create_llm()
        text_extractor = TextExtractor(llm=llm)
        pdf_extractor = PDFExtractor(text_extractor=text_extractor)
        detector = create_detector(llm=llm, search_mode="local")

        self.pipeline = ValidationPipeline(
            extractor=pdf_extractor, detector=detector, callbacks=[]
        )

        await self.task_store.initialize()
        await self.queue.connect()

        # Start metrics server in a separate thread
        start_http_server(8001)
        logger.info("Metrics server started", port=8001)

        logger.info("Worker initialized")

    def _setup_signal_handlers(self):
        def signal_handler():
            logger.info("Received shutdown signal...")
            self._shutdown_event.set()

        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, signal_handler)

    async def process_message(self, message: aio_pika.IncomingMessage):
        try:
            async with message.process():
                data = json.loads(message.body.decode())
                task_id = data["task_id"]
                filename = data["filename"]
                pdf_path = data["pdf_path"]
                search_mode = data.get("search_mode", "local")

                # Get retry count from database (tracks actual retries)
                task = await self.task_store.get_task(task_id)
                retry_count = task.get("retry_count", 0) if task else 0

                # Bind task_id to context so all subsequent logs include it
                structlog.contextvars.bind_contextvars(task_id=task_id)

                try:
                    logger.info(
                        "Processing task", filename=filename, retry_count=retry_count
                    )

                    # Update metrics: pending -> processing
                    tasks_active.labels(status="pending").dec()
                    tasks_active.labels(status="processing").inc()

                    await self.task_store.update_status(task_id, TaskStatus.PROCESSING)

                    start_time = time.time()

                    async with self.semaphore:
                        try:
                            result = await self.pipeline.process_pdf(
                                pdf_path, max_workers=5
                            )

                            references = [
                                {
                                    "title": item.get("paper", {}).get(
                                        "title", "Unknown"
                                    ),
                                    "authors": item.get("paper", {}).get("authors", []),
                                    "status": "real"
                                    if item.get("validation", {}).get(
                                        "hallucination_type"
                                    )
                                    == "Real"
                                    else "hallucination",
                                    "hallucination_type": item.get(
                                        "validation", {}
                                    ).get("hallucination_type"),
                                    "confidence": item.get("validation", {}).get(
                                        "confidence", 0
                                    ),
                                    "reasoning": item.get("validation", {}).get(
                                        "reasoning", ""
                                    ),
                                    "evidence": item.get("validation", {}).get(
                                        "evidence", []
                                    ),
                                }
                                for item in result.get("results", [])
                            ]

                            hallucination_count = sum(
                                1 for r in references if r["status"] == "hallucination"
                            )

                            formatted_result = {
                                "total_references": result.get("references_count", 0),
                                "validated_count": result.get("validated_count", 0),
                                "real_count": len(references) - hallucination_count,
                                "hallucination_count": hallucination_count,
                                "references": references,
                                "duration_seconds": result.get("duration_seconds", 0),
                            }

                            await self.task_store.update_status(
                                task_id, TaskStatus.COMPLETED, result=formatted_result
                            )

                            # Update metrics: completed
                            duration = time.time() - start_time
                            tasks_completed.inc()
                            task_duration_seconds.observe(duration)
                            tasks_active.labels(status="processing").dec()

                            logger.info(
                                "Task completed",
                                references_count=len(references),
                                duration_seconds=duration,
                            )

                        except Exception as e:
                            # Extract error_code from exception if available
                            error_code = get_error_code(e)

                            # Log with exc_info so structlog can format traceback properly
                            logger.error(
                                "Task processing error",
                                error=str(e),
                                error_code=error_code,
                                exc_info=True,
                            )

                            # Update metrics: failed
                            tasks_failed.labels(permanent="false").inc()
                            tasks_active.labels(status="processing").dec()

                            error_msg = f"{str(e)}\n{traceback.format_exc()}"

                            # Check if max retries exceeded
                            if retry_count >= RABBITMQ_MAX_RETRIES:
                                # Max retries exceeded: move to DLQ
                                await self._handle_failure(
                                    data, task_id, error_msg, error_code
                                )
                                # Swallow exception - message is manually handled (sent to DLQ)
                                return
                            else:
                                # Update retry count in database before letting RabbitMQ retry
                                await self.task_store.increment_retry(
                                    task_id,
                                    f"Attempt {retry_count + 1}/{RABBITMQ_MAX_RETRIES}: {error_msg[:500]}"
                                )
                                # Let RabbitMQ handle retry via DLX -> retry queue -> main queue
                                # Just raise to reject message
                                raise
                finally:
                    # Clear contextvars after task processing
                    structlog.contextvars.clear_contextvars()
        except Exception:
            # This should only happen for unexpected errors not caught in inner try-except
            # or when retry_count < max and we want to reject to DLX for retry
            # Message will be rejected to DLX -> retry queue -> main queue
            logger.debug("Message rejected for retry", task_id=data.get("task_id"))

    async def _handle_failure(
        self, data: dict, task_id: str, error_msg: str, error_code: Optional[str] = None
    ):
        """Handle task failure. Called when max retries exceeded.

        Note: Normal retries are handled automatically by RabbitMQ via DLX -> retry queue.
        This method is only called when retry_count > RABBITMQ_MAX_RETRIES.
        """
        retry_count = data.get("retry_count", 0)

        # Mark as permanently failed in database
        await self.task_store.update_status(
            task_id,
            TaskStatus.FAILED_PERMANENTLY,
            error_code=error_code,
            error_message=f"Max retries ({RABBITMQ_MAX_RETRIES}) exceeded: {error_msg[:1000]}",
        )

        # Update metrics
        tasks_failed.labels(permanent="true").inc()

        # Send to DLQ manually (since RabbitMQ doesn't know about max retries)
        await self.queue.publish_to_dlq(
            task_id,
            data["filename"],
            data["pdf_path"],
            data.get("search_mode", "local"),
            retry_count,
            error_msg,
        )

        logger.info(
            "Task moved to DLQ after max retries",
            task_id=task_id,
            retry_count=retry_count,
        )

    async def run(self):
        await self.initialize()
        self._setup_signal_handlers()

        channel = self.queue.channel
        await channel.set_qos(prefetch_count=WORKER_PREFETCH_COUNT)

        logger.info(
            "PDF Worker started",
            concurrency=WORKER_CONCURRENCY,
            prefetch=WORKER_PREFETCH_COUNT,
        )
        logger.info("Press Ctrl+C to stop gracefully")

        await self.queue.consume(self.process_message)

        try:
            await self._shutdown_event.wait()
        finally:
            logger.info("Shutting down worker...")
            await self.queue.close()
            await self.task_store.close()
            logger.info("Worker stopped")


if __name__ == "__main__":
    worker = PDFValidationWorker()
    asyncio.run(worker.run())
