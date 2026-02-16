import concurrent.futures
from typing import List, Dict, Any, Optional
from pathlib import Path
import time
import json

from .extract import PDFExtractor
from .detector import HallucinationDetector, ValidationResult
from .logger import logger
from ..bench.schema import Paper

class ValidationPipeline:
    """
    Pipeline for extracting references from a PDF and validating them against external sources.
    """
    def __init__(self):
        logger.info("Initializing ValidationPipeline...")
        self.extractor = PDFExtractor()
        self.detector = HallucinationDetector()

    def process_pdf(self, pdf_path: str, max_workers: int = 5) -> Dict[str, Any]:
        """
        Process a PDF file: extract references and validate them concurrently.
        
        Args:
            pdf_path: Path to the PDF file.
            max_workers: Number of concurrent validation threads.
            
        Returns:
            Dictionary containing processing metadata and list of validation results.
        """
        start_time = time.time()
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        logger.info(f"Starting extraction for: {path.name}")
        try:
            references = self.extractor.extract(str(path))
            logger.info(f"Extracted {len(references)} references.")
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return {
                "file": path.name,
                "status": "failed",
                "error": str(e),
                "references_count": 0,
                "results": []
            }

        if not references:
            logger.warning("No references found.")
            return {
                "file": path.name,
                "status": "completed",
                "references_count": 0,
                "results": []
            }

        logger.info(f"Starting validation for {len(references)} references with {max_workers} workers...")
        results = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_paper = {
                executor.submit(self._validate_single_reference, paper, i, len(references)): paper 
                for i, paper in enumerate(references)
            }
            
            for future in concurrent.futures.as_completed(future_to_paper):
                paper = future_to_paper[future]
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                except Exception as e:
                    logger.error(f"Validation failed for reference '{paper.title}': {e}")
                    # Add a failed result entry
                    results.append({
                        "paper": paper.model_dump(),
                        "validation": {
                            "is_hallucination": None,
                            "confidence": 0.0,
                            "reasoning": f"Validation process error: {str(e)}",
                            "evidence": []
                        },
                        "status": "error"
                    })

        end_time = time.time()
        duration = end_time - start_time
        
        summary = {
            "file": path.name,
            "status": "completed",
            "duration_seconds": duration,
            "references_count": len(references),
            "validated_count": len(results),
            "results": results
        }
        
        logger.info(f"Pipeline completed in {duration:.2f} seconds.")
        return summary

    def _validate_single_reference(self, paper: Paper, index: int, total: int) -> Dict[str, Any]:
        """
        Validate a single reference using the detector.
        """
        logger.info(f"Validating [{index+1}/{total}]: {paper.title[:50]}...")
        try:
            validation_result = self.detector.check_reference(paper)
            return {
                "paper": paper.model_dump(),
                "validation": validation_result.model_dump(),
                "status": "success"
            }
        except Exception as e:
            logger.error(f"Error checking reference '{paper.title}': {e}")
            raise e
