import asyncio
from typing import Dict, Any, List, Optional
from pathlib import Path
import time

from .extract import PDFExtractor
from .detector import HallucinationDetector
from .logger import logger
from .exceptions import ExtractionError, ValidationError, ValidationTimeoutError, AgentParseError, SearchError
from ..bench.schema import Paper
from .callbacks import ValidationCallback


class ValidationPipeline:
    """
    Pipeline for extracting references from a PDF and validating them against external sources.
    """

    def __init__(
        self,
        extractor: Optional[PDFExtractor] = None,
        detector: Optional[HallucinationDetector] = None,
        callbacks: Optional[List[ValidationCallback]] = None,
    ):
        logger.info("Initializing ValidationPipeline...")
        self.extractor = extractor if extractor is not None else PDFExtractor()
        self.detector = detector if detector is not None else HallucinationDetector()
        self.callbacks = callbacks or []

    async def process_pdf(self, pdf_path: str, max_workers: int = 10) -> Dict[str, Any]:
        """
        Process a PDF file: extract references and validate them concurrently.
        """
        start_time = time.time()
        path = Path(pdf_path)

        self._check_file_exists(path)

        logger.info(f"Starting extraction for: {path.name}")
        self._notify_callbacks("on_pipeline_start", path.name)
        self._notify_callbacks("on_extraction_start", path.name)

        try:
            references = await self.extractor.extract(str(path))

            logger.info(f"Extracted {len(references)} references.")
            self._notify_callbacks("on_extraction_end", references)

        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            self._notify_callbacks("on_error", e)
            raise ExtractionError(f"Failed to extract references from {path.name}: {e}") from e

        if not references:
            logger.warning("No references found.")
            return self._create_summary(path.name, start_time)

        logger.info(
            f"Starting validation for {len(references)} references with {max_workers} workers..."
        )
        self._notify_callbacks("on_validation_start", len(references))

        results = []
        try:
            results = await self._run_validation(references, max_workers)
        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            self._notify_callbacks("on_error", e)
            raise e

        summary = self._create_summary(
            path.name, start_time, references_count=len(references), results=results
        )

        logger.info(
            f"Pipeline {summary['status']} in {summary['duration_seconds']:.2f} seconds."
        )
        self._notify_callbacks("on_pipeline_end", summary)

        return summary

    def _check_file_exists(self, path: Path):
        if not path.exists():
            error = FileNotFoundError(f"PDF file not found: {path}")
            self._notify_callbacks("on_error", error)
            raise error

    async def _run_validation(
        self, references: List[Paper], max_workers: int
    ) -> List[Dict[str, Any]]:
        results = []
        semaphore = asyncio.Semaphore(max_workers)

        async def sem_task(index, paper):
            async with semaphore:
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
                    self._notify_callbacks(
                        "on_reference_validation_end", references[index], result
                    )
            except (ValidationError, ValidationTimeoutError, AgentParseError, SearchError) as e:
                # Business exceptions are already handled in _validate_single_reference
                # This should not happen, but log just in case
                logger.warning(f"Unexpected business exception in task: {e}")
            except Exception as e:
                # Unexpected exceptions: re-raise to fail the entire task
                logger.error(f"Unexpected task error: {e}")
                raise

        return results

    async def _validate_single_reference(
        self, paper: Paper, index: int, total: int
    ) -> Optional[Dict[str, Any]]:
        """
        Validate a single reference using the detector asynchronously.
        """
        logger.info(f"Validating [{index + 1}/{total}]: {paper.title[:50]}...")
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
            logger.error(f"Validation failed for reference '{paper.title}': {e}")
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
            logger.error(f"Unexpected error checking reference '{paper.title}': {e}")
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
        """Helper to notify all callbacks safely."""
        for callback in self.callbacks:
            if hasattr(callback, method_name):
                getattr(callback, method_name)(*args, **kwargs)
