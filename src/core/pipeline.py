import asyncio
from typing import Dict, Any, List, Optional
from pathlib import Path
import time

from .extract import PDFExtractor
from .detector import HallucinationDetector
from .logger import logger
from ..bench.schema import Paper
from .callbacks import ValidationCallback


class ValidationPipeline:
    """
    Pipeline for extracting references from a PDF and validating them against external sources.
    """

    def __init__(self, callbacks: Optional[List[ValidationCallback]] = None):
        logger.info("Initializing ValidationPipeline...")
        self.extractor = PDFExtractor()
        self.detector = HallucinationDetector()
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
            return self._create_summary(
                path.name, start_time, error=str(e), status="failed"
            )

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
            except Exception as e:
                logger.error(f"Task error: {e}")

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

        except Exception as e:
            logger.error(f"Error checking reference '{paper.title}': {e}")
            self._notify_callbacks("on_reference_validation_error", paper, e)
            return {
                "paper": paper.model_dump(),
                "validation": {
                    "is_hallucination": None,
                    "confidence": 0.0,
                    "reasoning": f"Validation process error: {str(e)}",
                    "evidence": [],
                },
                "status": "error",
            }

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
