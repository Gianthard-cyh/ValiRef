from pydantic import BaseModel
from typing import Optional, List, Dict
from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"
    FAILED_PERMANENTLY = "failed_permanently"


class PDFValidationResponse(BaseModel):
    """PDF提交后的响应"""
    task_id: str
    status: TaskStatus
    filename: str
    message: str


class ReferenceResult(BaseModel):
    """单个引用的验证结果"""
    title: str
    authors: List[str]
    venue: Optional[str] = None
    ccf_rank: Optional[str] = None
    status: str
    hallucination_type: Optional[str] = None
    confidence: float
    reasoning: str
    evidence: List[str] = []


class PDFValidationResult(BaseModel):
    """PDF完整验证结果"""
    task_id: str
    filename: str
    status: TaskStatus
    total_references: int
    validated_count: int
    real_count: int
    hallucination_count: int
    references: List[ReferenceResult]
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None


class TaskStatusResponse(BaseModel):
    """任务状态查询响应"""
    task_id: str
    status: TaskStatus
    filename: str
    error_code: Optional[str] = None
    stage: Optional[str] = None  # extraction | validation | completed
    progress: Optional[dict] = None
    current_title: Optional[str] = None  # 当前正在验证的引用标题
    created_at: str
    completed_at: Optional[str] = None


class QueueStatsResponse(BaseModel):
    """队列统计响应"""
    total: int
    by_status: Dict[str, int]
