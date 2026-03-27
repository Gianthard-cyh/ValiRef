import asyncpg
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from ...core.config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class TaskStore:
    def __init__(self):
        self.pool = None

    async def initialize(self):
        logger.debug(f"Connecting to PostgreSQL: {DB_HOST}:{DB_PORT}/{DB_NAME}")

        async def init_connection(conn):
            logger.debug(
                f"[asyncpg] New connection established: {conn.get_server_version()}"
            )
            await conn.set_type_codec(
                "json", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
            )
            await conn.set_type_codec(
                "jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
            )

        self.pool = await asyncpg.create_pool(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            min_size=2,
            max_size=10,
            command_timeout=60,
            init=init_connection,
            server_settings={"application_name": "valiref_worker"},
        )
        logger.info("PostgreSQL connection pool created")

        async with self.pool.acquire() as conn:
            logger.debug("Creating table pdf_validation_tasks if not exists")
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS pdf_validation_tasks (
                    task_id VARCHAR(36) PRIMARY KEY,
                    status VARCHAR(20) NOT NULL CHECK (status IN (
                        'pending', 'processing', 'retrying', 'completed', 'failed', 'failed_permanently'
                    )),
                    filename VARCHAR(255) NOT NULL,
                    pdf_path TEXT,
                    request_data JSONB NOT NULL,
                    result JSONB,
                    error_message TEXT,
                    retry_count INTEGER DEFAULT 0,
                    progress_processed INTEGER DEFAULT 0,
                    progress_total INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_pdf_task_status ON pdf_validation_tasks(status);
                CREATE INDEX IF NOT EXISTS idx_pdf_task_created_at ON pdf_validation_tasks(created_at);
            """)
            logger.debug("Table pdf_validation_tasks ready")

    async def create_task(
        self, task_id: str, filename: str, pdf_path: str, request_data: dict
    ) -> dict:
        logger.debug(f"[SQL] INSERT task {task_id}: {filename}")
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO pdf_validation_tasks
                   (task_id, status, filename, pdf_path, request_data)
                   VALUES ($1, $2, $3, $4, $5)
                   RETURNING task_id, status, filename, created_at""",
                task_id,
                "pending",
                filename,
                pdf_path,
                json.dumps(request_data),
            )
            logger.debug(f"[SQL] INSERT task {task_id} success")
            return dict(row)

    async def get_task(self, task_id: str) -> Optional[dict]:
        logger.debug(f"[SQL] SELECT task {task_id}")
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM pdf_validation_tasks WHERE task_id = $1", task_id
            )
            logger.debug(
                f"[SQL] SELECT task {task_id}: {'found' if row else 'not found'}"
            )
            return dict(row) if row else None

    async def update_status(
        self,
        task_id: str,
        status: str,
        result: Optional[dict] = None,
        error_message: Optional[str] = None,
        progress_processed: Optional[int] = None,
        progress_total: Optional[int] = None,
    ):
        async with self.pool.acquire() as conn:
            completed_at = None
            if status in ("completed", "failed", "failed_permanently"):
                completed_at = datetime.now()

            await conn.execute(
                """UPDATE pdf_validation_tasks
                   SET status = $2,
                       result = $3,
                       error_message = $4,
                       progress_processed = COALESCE($5, progress_processed),
                       progress_total = COALESCE($6, progress_total),
                       completed_at = COALESCE($7, completed_at),
                       updated_at = CURRENT_TIMESTAMP
                   WHERE task_id = $1""",
                task_id,
                status,
                json.dumps(result) if result else None,
                error_message,
                progress_processed,
                progress_total,
                completed_at,
            )

    async def increment_retry(self, task_id: str, error_message: str) -> int:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """UPDATE pdf_validation_tasks
                   SET retry_count = retry_count + 1,
                       error_message = $2,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE task_id = $1
                   RETURNING retry_count""",
                task_id,
                error_message,
            )
            return row["retry_count"] if row else 0

    async def get_status_stats(self) -> dict:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT status, COUNT(*) FROM pdf_validation_tasks GROUP BY status"
            )
            return {row["status"]: row["count"] for row in rows}

    async def get_dlq_count(self) -> int:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT COUNT(*) FROM pdf_validation_tasks WHERE status = 'failed_permanently'"
            )
            return row["count"]

    async def close(self):
        if self.pool:
            await self.pool.close()
