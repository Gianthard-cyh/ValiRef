from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager

from src.core.logger import set_logger_mode, get_logger
from .routers import validation
from .services.queue import MessageQueue
from .services.task_store import TaskStore

# Configure logging for backend (JSON format)
set_logger_mode("json")
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    queue = MessageQueue()
    task_store = TaskStore()

    try:
        await queue.connect()
        app.state.queue = queue
        logger.info("Connected to RabbitMQ")
    except Exception as e:
        logger.error(f"Failed to connect to RabbitMQ: {e}")
        raise RuntimeError(f"RabbitMQ connection failed: {e}") from e

    try:
        await task_store.initialize()
        app.state.task_store = task_store
        logger.info("Connected to PostgreSQL")
    except Exception as e:
        logger.error(f"Failed to connect to PostgreSQL: {e}")
        await queue.close()
        raise RuntimeError(f"PostgreSQL connection failed: {e}") from e

    yield

    await queue.close()
    await task_store.close()


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
