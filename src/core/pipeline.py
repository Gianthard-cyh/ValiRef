import asyncio
from typing import Dict, Any, List, Optional
from pathlib import Path
import time

from .extract import Extractor, PDFExtractor
from .detector import HallucinationDetector
from .logger import logger
from .exceptions import (
    ExtractionError,
    ValidationError,
    ValidationTimeoutError,
    AgentParseError,
    SearchError,
    get_error_code,
)
from ..bench.schema import Paper, Reference
from .callbacks import ValidationCallback
from .state import ValidationPhase, PipelineState


class ValidationPipeline:
    """
    Pipeline for extracting references from a PDF and validating them against external sources.
    """

    def __init__(
        self,
        extractor: Optional[Extractor] = None,
        detector: Optional[HallucinationDetector] = None,
        callbacks: Optional[List[ValidationCallback]] = None,
    ):
        logger.info("Initializing ValidationPipeline...")
        self.extractor = extractor if extractor is not None else PDFExtractor()
        self.detector = detector if detector is not None else HallucinationDetector()
        self.callbacks = callbacks or []
        self.state = PipelineState()

    async def process(self, file_path: str, max_workers: int = 10) -> Dict[str, Any]:
        """
        Process a file: extract references and validate them concurrently.
        """
        start_time = time.time()
        path = Path(file_path)

        self._check_file_exists(path)

        # Initialize state
        self.state = PipelineState(current_file=path.name)

        logger.info("Starting extraction", filename=path.name)
        self._notify_callbacks("on_pipeline_start", path.name)

        try:
            # Extraction phase
            self._set_phase(ValidationPhase.EXTRACTION)
            self._notify_callbacks("on_extraction_start", path.name)

            references = await self.extractor.extract(
                str(path),
                on_progress=self._on_extraction_progress,
            )

            logger.info("Extracted references", reference_count=len(references))
            self._notify_callbacks("on_extraction_end", references)

        except Exception as e:
            self._set_phase(ValidationPhase.ERROR)
            self.state.error = str(e)
            logger.error("Extraction failed", error=str(e))
            self._notify_callbacks("on_error", e)
            error_code = get_error_code(e)
            raise ExtractionError(
                f"Failed to extract references from {path.name}: {e}",
                error_code=error_code
            ) from e

        if not references:
            logger.warning("No references found.")
            return self._create_summary(path.name, start_time)

        # Detection phase
        self._set_phase(ValidationPhase.DETECTION)
        self.state.detection_total = len(references)

        logger.info(
            "Starting validation",
            reference_count=len(references),
            worker_count=max_workers
        )
        self._notify_callbacks("on_validation_start", len(references))

        results = []
        try:
            results = await self._run_validation(references, max_workers)
        except Exception as e:
            self._set_phase(ValidationPhase.ERROR)
            self.state.error = str(e)
            logger.error("Pipeline failed", error=str(e))
            self._notify_callbacks("on_error", e)
            raise e

        # Completion
        self._set_phase(ValidationPhase.COMPLETED)
        summary = self._create_summary(
            path.name, start_time, references_count=len(references), results=results
        )

        logger.info(
            "Pipeline completed",
            status=summary['status'],
            duration_seconds=summary['duration_seconds']
        )
        self._notify_callbacks("on_pipeline_end", summary)

        return summary

    def _set_phase(self, phase: ValidationPhase):
        """Update pipeline phase and notify callbacks."""
        self.state.phase = phase
        self._notify_callbacks("on_phase_change", self.state)

    def _on_extraction_progress(self, count: int, new_refs: List[Reference]):
        """Handle extraction progress updates."""
        self.state.extraction_found = count
        self.state.extracted_refs.extend(new_refs)
        self._notify_callbacks("on_extraction_progress", self.state, new_refs)

    def _check_file_exists(self, path: Path):
        if not path.exists():
            error = FileNotFoundError(f"File not found: {path}")
            self._notify_callbacks("on_error", error)
            raise error

    async def _run_validation(
        self, references: List[Paper], max_workers: int
    ) -> List[Dict[str, Any]]:
        results = []
        semaphore = asyncio.Semaphore(max_workers)

        async def sem_task(index, paper):
            async with semaphore:
                # Update current reference in state
                self.state.current_reference = paper.title[:100] if paper.title else "Unknown"
                res = await self._validate_single_reference(
                    paper, index, len(references)
                )
                return index, res

        tasks = [sem_task(i, paper) for i, paper in enumerate(references)]

        for future in asyncio.as_completed(tasks):
            try:
                index, result = await future
                if result:
                    results.append(result)
                    self.state.detection_processed += 1
                    self._notify_callbacks(
                        "on_reference_validation_end", references[index], result
                    )
            except (ValidationError, ValidationTimeoutError, AgentParseError, SearchError) as e:
                # Business exceptions are already handled in _validate_single_reference
                # This should not happen, but log just in case
                logger.warning("Unexpected business exception in task", error=str(e))
            except Exception as e:
                # Unexpected exceptions: re-raise to fail the entire task
                logger.error("Unexpected task error", error=str(e))
                raise

        return results

    async def _validate_single_reference(
        self, paper: Paper, index: int, total: int
    ) -> Optional[Dict[str, Any]]:
        """
        Validate a single reference using the detector asynchronously.
        """
        logger.info("Validating reference", index=index + 1, total=total, title=paper.title[:50])
        self._notify_callbacks("on_reference_validation_start", paper, index, total)

        try:
            # Use the async check method
            validation_result = await self.detector.check_reference(paper)

            result = {
                "paper": paper.model_dump(),
                "validation": validation_result.model_dump(),
                "status": "success",
            }
            return result

        except (ValidationError, ValidationTimeoutError, AgentParseError, SearchError) as e:
            # Business exceptions: convert to error result, task continues
            logger.error("Validation failed for reference", reference_title=paper.title, error=str(e))
            self._notify_callbacks("on_reference_validation_error", paper, e)
            return {
                "paper": paper.model_dump(),
                "validation": {
                    "is_hallucination": None,
                    "confidence": 0.0,
                    "reasoning": f"Validation failed: {str(e)}",
                    "evidence": [],
                },
                "status": "error",
            }
        except Exception as e:
            # Unknown exceptions: raise to fail the entire task
            logger.error("Unexpected error checking reference", reference_title=paper.title, error=str(e))
            raise

    def _create_summary(
        self,
        filename: str,
        start_time: float,
        references_count: int = 0,
        results: List = None,
        error: str = None,
        status: str = "completed",
    ) -> Dict[str, Any]:
        end_time = time.time()
        summary = {
            "file": filename,
            "status": status,
            "duration_seconds": end_time - start_time,
            "references_count": references_count,
            "validated_count": len(results) if results else 0,
            "results": results or [],
        }
        if error:
            summary["error"] = error
        return summary

    def _notify_callbacks(self, method_name: str, *args, **kwargs):
        """Helper to notify all callbacks safely without blocking."""
        for callback in self.callbacks:
            if hasattr(callback, method_name):
                method = getattr(callback, method_name)
                # All callbacks are now async, start in background
                task = asyncio.create_task(method(*args, **kwargs))
                task.add_done_callback(self._on_callback_done)

    def _on_callback_done(self, task):
        """Handle callback task completion and log any exceptions."""
        try:
            task.result()
        except Exception as e:
            logger.error("Callback task failed", error=str(e))
