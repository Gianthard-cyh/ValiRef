"""Worker progress callback for updating task progress in database."""
import time
from typing import List, Dict, Any

from ..services.task_store import TaskStore
from ...core.callbacks import ValidationCallback
from ...bench.schema import Paper, Reference
from ...core.state import PipelineState
from ...core.logger import get_logger

logger = get_logger(__name__)


class WorkerProgressCallback(ValidationCallback):
    """Callback that updates task progress in database for real-time monitoring."""

    def __init__(self, task_store: TaskStore, task_id: str):
        self.task_store = task_store
        self.task_id = task_id
        self.start_time = time.time()
        self.stage = "extraction"  # extraction | validation | completed
        self.processed = 0
        self.total = 0
        self.current_title = None

    async def on_pipeline_start(self, filename: str):
        """Called when pipeline starts."""
        logger.info("Pipeline started", task_id=self.task_id, filename=filename)
        await self._update_progress()

    async def on_extraction_start(self, filename: str):
        """Called when reference extraction starts."""
        self.stage = "extraction"
        logger.info("Extraction started", task_id=self.task_id)
        await self._update_progress()

    async def on_extraction_end(self, references: List[Paper]):
        """Called when reference extraction completes."""
        self.stage = "validation"
        self.total = len(references)
        logger.info(
            "Extraction completed",
            task_id=self.task_id,
            reference_count=self.total
        )
        await self._update_progress()

    async def on_validation_start(self, total_references: int):
        """Called when validation of references starts."""
        self.stage = "validation"
        self.total = total_references
        logger.info(
            "Validation started",
            task_id=self.task_id,
            total=total_references
        )
        await self._update_progress()

    async def on_reference_validation_start(self, paper: Paper, index: int, total: int):
        """Called before validating a single reference."""
        self.current_title = paper.title[:100] if paper.title else "Unknown"
        logger.debug(
            "Validating reference",
            task_id=self.task_id,
            index=index + 1,
            total=total,
            title=self.current_title
        )
        # Throttle updates to avoid overwhelming the database
        if index % 5 == 0 or index == total - 1:  # Update every 5 references or at the end
            await self._update_progress()

    async def on_reference_validation_end(self, paper: Paper, result: Dict[str, Any]):
        """Called after validating a single reference."""
        self.processed += 1

    async def on_reference_validation_error(self, paper: Paper, error: Exception):
        """Called when validation fails for a reference."""
        self.processed += 1
        logger.warning(
            "Reference validation failed",
            task_id=self.task_id,
            title=paper.title[:50] if paper.title else "Unknown",
            error=str(error)
        )

    async def on_pipeline_end(self, results: Dict[str, Any]):
        """Called when pipeline completes."""
        self.stage = "completed"
        duration = time.time() - self.start_time
        logger.info(
            "Pipeline completed",
            task_id=self.task_id,
            duration_seconds=duration,
            references_count=self.total
        )
        await self._update_progress()

    async def on_error(self, error: Exception):
        """Called when a critical pipeline error occurs."""
        logger.error(
            "Pipeline error",
            task_id=self.task_id,
            error=str(error)
        )

    async def on_phase_change(self, state: PipelineState):
        """Called when pipeline phase changes."""
        self.stage = state.phase.value
        self.total = max(self.total, state.extraction_found, state.detection_total)
        logger.info(
            "Phase changed",
            task_id=self.task_id,
            phase=self.stage,
        )
        await self._update_progress()

    async def on_extraction_progress(self, state: PipelineState, new_refs: List[Reference]):
        """Called during streaming extraction when new references are found."""
        self.total = state.extraction_found
        logger.debug(
            "Extraction progress",
            task_id=self.task_id,
            found=state.extraction_found,
            new_refs=len(new_refs),
        )
        # Update progress in real-time for extraction phase
        await self._update_progress()

    async def _update_progress(self):
        """Update progress in database."""
        try:
            await self.task_store.update_progress(
                task_id=self.task_id,
                stage=self.stage,
                processed=self.processed,
                total=self.total,
                current_title=self.current_title
            )
        except Exception as e:
            logger.error(
                "Failed to update progress",
                task_id=self.task_id,
                error=str(e)
            )
