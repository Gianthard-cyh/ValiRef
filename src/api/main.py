from fastapi import FastAPI, HTTPException, Response
from contextlib import asynccontextmanager
import asyncio
import json

from src.core.logger import set_logger_mode, get_logger
from .routers import validation
from .services.queue import MessageQueue
from .services.task_store import TaskStore
from .services.metrics import get_metrics
from .services.sse_manager import SSEManager

# Configure logging for backend (JSON format)
set_logger_mode("json")
logger = get_logger(__name__)


async def start_progress_consumer(queue: MessageQueue, sse_manager: SSEManager):
    """Consume progress updates from RabbitMQ and broadcast to SSE clients."""
    async def on_message(message):
        try:
            data = json.loads(message.body.decode())
            task_id = data.get("task_id")
            # Broadcast to all SSE clients watching this task
            await sse_manager.broadcast(task_id, data)
            await message.ack()
        except Exception as e:
            logger.error("Failed to process progress update", error=str(e))
            await message.nack(requeue=True)

    # Consume from progress_updates queue
    await queue.progress_queue.consume(on_message)
    logger.info("Started progress updates consumer")


@asynccontextmanager
async def lifespan(app: FastAPI):
    queue = MessageQueue()
    task_store = TaskStore()
    sse_manager = SSEManager()

    try:
        await queue.connect()
        app.state.queue = queue
        logger.info("Connected to RabbitMQ")
    except Exception as e:
        logger.error("Failed to connect to RabbitMQ", error=str(e))
        raise RuntimeError(f"RabbitMQ connection failed: {e}") from e

    try:
        await task_store.initialize()
        app.state.task_store = task_store
        logger.info("Connected to PostgreSQL")
    except Exception as e:
        logger.error("Failed to connect to PostgreSQL", error=str(e))
        await queue.close()
        raise RuntimeError(f"PostgreSQL connection failed: {e}") from e

    # Initialize SSE manager
    app.state.sse_manager = sse_manager
    logger.info("SSE manager initialized")

    # Start progress updates consumer
    try:
        await start_progress_consumer(queue, sse_manager)
    except Exception as e:
        logger.error("Failed to start progress consumer", error=str(e))

    yield

    await queue.close()
    await task_store.close()
    logger.info("Cleanup complete")


app = FastAPI(
    title="ValiRef API",
    description="AI-Powered Citation Validation Service for PDF Documents",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(validation.router)


@app.get("/health")
async def health_check():
    """Health check endpoint that verifies dependencies"""
    try:
        # Check PostgreSQL connectivity
        task_store = app.state.task_store
        await task_store.get_task("health-check")

        # Check RabbitMQ connectivity
        queue = app.state.queue
        if queue.connection.is_closed:
            raise HTTPException(status_code=503, detail="RabbitMQ connection closed")

        return {"status": "healthy", "service": "valiref-api"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    data, content_type = get_metrics()
    return Response(content=data, media_type=content_type)
