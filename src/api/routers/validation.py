from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import StreamingResponse
from uuid import uuid4
import json
import asyncio

from ..schemas.api import (
    PDFValidationResponse,
    PDFValidationResult,
    TaskStatusResponse,
    QueueStatsResponse,
    TaskStatus,
)
from ..services.pdf_storage import PDFStorage
from ...core.config import API_MAX_UPLOAD_SIZE
from ...core.venue_rank import get_venue_rank_lookup

router = APIRouter(prefix="/validation", tags=["validation"])


@router.post("/submit", response_model=PDFValidationResponse)
async def submit_pdf(
    request: Request,
    file: UploadFile = File(..., description="PDF file to validate"),
    search_mode: str = Form(
        default="local", description="Search mode: local or online"
    ),
):
    """提交PDF验证请求"""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    content = await file.read()
    if len(content) > API_MAX_UPLOAD_SIZE * 1024 * 1024:
        raise HTTPException(
            status_code=413, detail=f"File too large, max {API_MAX_UPLOAD_SIZE}MB"
        )

    task_id = str(uuid4())

    pdf_storage = PDFStorage()
    pdf_path = await pdf_storage.save(task_id, file.filename, content)

    task_store = request.app.state.task_store
    await task_store.create_task(
        task_id=task_id,
        filename=file.filename,
        pdf_path=pdf_path,
        request_data={"search_mode": search_mode, "original_filename": file.filename},
    )

    # Update metrics
    from ..services.metrics import tasks_submitted, tasks_active
    tasks_submitted.inc()
    tasks_active.labels(status="pending").inc()

    queue = request.app.state.queue
    await queue.publish_pdf_task(task_id, file.filename, pdf_path, search_mode)

    return PDFValidationResponse(
        task_id=task_id,
        status=TaskStatus.PENDING,
        filename=file.filename,
        message="PDF validation request queued successfully",
    )


@router.get("/result/{task_id}", response_model=PDFValidationResult)
async def get_result(request: Request, task_id: str):
    """查询PDF验证结果"""
    task_store = request.app.state.task_store
    task = await task_store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    result = task.get("result")
    if isinstance(result, str):
        result = json.loads(result) or {}
    elif result is None:
        result = {}

    # Enrich references with CCF rank
    venue_rank_lookup = get_venue_rank_lookup()
    for ref in result.get("references", []):
        venue = ref.get("venue")
        rank_info = venue_rank_lookup.lookup(venue) if venue else None
        ref["ccf_rank"] = rank_info.ccf_rank if rank_info else None

    return PDFValidationResult(
        task_id=task["task_id"],
        filename=task["filename"],
        status=task["status"],
        total_references=result.get("total_references", 0),
        validated_count=result.get("validated_count", 0),
        real_count=result.get("real_count", 0),
        hallucination_count=result.get("hallucination_count", 0),
        references=result.get("references", []),
        error_code=task.get("error_code"),
        error_message=task.get("error_message"),
        created_at=task["created_at"].isoformat() if task.get("created_at") else "",
        completed_at=task["completed_at"].isoformat()
        if task.get("completed_at")
        else None,
        duration_seconds=result.get("duration_seconds"),
    )


@router.get("/status/{task_id}", response_model=TaskStatusResponse)
async def get_status(request: Request, task_id: str):
    """查询任务状态（轻量级，不包含完整结果）"""
    task_store = request.app.state.task_store
    task = await task_store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return TaskStatusResponse(
        task_id=task["task_id"],
        status=task["status"],
        filename=task["filename"],
        error_code=task.get("error_code"),
        stage=task.get("stage"),
        progress={
            "processed": task.get("progress_processed", 0),
            "total": task.get("progress_total", 0),
        }
        if task.get("progress_total", 0) > 0
        else None,
        current_title=task.get("current_title"),
        created_at=task["created_at"].isoformat() if task.get("created_at") else "",
        completed_at=task["completed_at"].isoformat()
        if task.get("completed_at")
        else None,
    )


@router.get("/stats", response_model=QueueStatsResponse)
async def get_stats(request: Request):
    """获取队列统计信息"""
    task_store = request.app.state.task_store
    stats = await task_store.get_status_stats()
    return QueueStatsResponse(
        total=sum(stats.values()),
        by_status=stats,
    )


@router.get("/stream/{task_id}")
async def stream_task_status(task_id: str, request: Request):
    """SSE endpoint for real-time task progress updates."""
    sse_manager = request.app.state.sse_manager
    task_store = request.app.state.task_store

    # Verify task exists
    task = await task_store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Register SSE connection
    queue = await sse_manager.connect(task_id)

    async def event_generator():
        try:
            # Send initial state
            initial_data = {
                "task_id": task_id,
                "stage": task.get("stage", "extraction"),
                "processed": task.get("progress_processed", 0),
                "total": task.get("progress_total", 0),
                "current_title": task.get("current_title"),
                "status": task.get("status", "pending"),
            }
            yield f"data: {json.dumps(initial_data)}\n\n"

            # Listen for updates
            while True:
                if await request.is_disconnected():
                    break

                try:
                    # Wait for message from MQ with timeout
                    data = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {json.dumps(data)}\n\n"

                    # Stop if task is complete or failed
                    if data.get("status") in ["completed", "failed", "failed_permanently"]:
                        break
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    yield ": heartbeat\n\n"
        except Exception as e:
            logger = get_logger(__name__)
            logger.error("SSE error", task_id=task_id, error=str(e))
        finally:
            await sse_manager.disconnect(task_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
