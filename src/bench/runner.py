"""Benchmark runner."""
import asyncio
import csv
import random
import time
from typing import TYPE_CHECKING, List, Optional

from rich.console import Console
from rich.console import Group
from rich.live import Live
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

from src.core.logger import logger
from src.core.tool_monitor import ToolMetricsCollector
from src.bench.schema import Paper
from src.bench.metrics.calculation import _calculate_multiclass_metrics
from src.bench.metrics.dataclasses import BenchmarkResult, MultiClassMetrics, SampleResult

if TYPE_CHECKING:
    from src.core.detector import HallucinationDetector, ValidationResult


class BenchmarkRunner:
    """Runner for benchmarking hallucination detection performance."""

    def __init__(self, detector: "HallucinationDetector"):
        self.detector = detector
        self.console = Console()

    def _load_dataset(self, path: str) -> List[Paper]:
        """Load dataset from CSV file."""
        papers = []
        with open(path, "r", newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                # Parse list fields (authors, claims) that are "; " separated
                authors = []
                if row.get("authors"):
                    authors = [
                        a.strip() for a in row["authors"].split(";") if a.strip()
                    ]

                claims = []
                if row.get("claims"):
                    claims = [c.strip() for c in row["claims"].split(";") if c.strip()]

                paper = Paper(
                    source=row.get("source", ""),
                    id=row.get("id", ""),
                    title=row.get("title", ""),
                    abstract=row.get("abstract", ""),
                    authors=authors,
                    published_date=row.get("published_date", ""),
                    updated_date=row.get("updated_date") or None,
                    url=row.get("url", ""),
                    pdf_url=row.get("pdf_url") or None,
                    claims=claims,
                    hallucination_type=row.get("hallucination_type") or None,
                    original_paper_id=row.get("original_paper_id") or None,
                    venue=row.get("venue") or None,
                )
                papers.append(paper)

        logger.info(f"Loaded {len(papers)} papers from {path}")
        return papers

    def _get_ground_truth_type(self, paper: Paper) -> str:
        """Determine the ground truth hallucination type."""
        if not paper.hallucination_type:
            return "Real"
        # Normalize case variations
        type_mapping = {
            "fabrication": "Fabrication",
            "attributionerror": "AttributionError",
            "attribution_error": "AttributionError",
            "irrelevance": "Irrelevance",
            "counterfactual": "Counterfactual",
        }
        normalized = paper.hallucination_type.strip()
        return type_mapping.get(normalized.lower(), normalized)

    async def run(
        self,
        dataset_path: str,
        max_workers: int = 5,
        limit: Optional[int] = None,
        verbose: bool = False,
        show_metrics: bool = True,
    ) -> BenchmarkResult:
        """
        Run benchmark on the dataset.

        Args:
            dataset_path: Path to the CSV dataset file
            max_workers: Number of concurrent validation workers
            limit: Optional limit on number of samples to test
            verbose: Enable verbose output
            show_metrics: Show real-time tool call metrics

        Returns:
            BenchmarkResult with metrics and sample results
        """
        start_time = time.time()

        # Load dataset
        papers = self._load_dataset(dataset_path)
        random.shuffle(papers)
        if limit and limit > 0:
            papers = papers[:limit]

        logger.info(
            f"Running benchmark on {len(papers)} samples with {max_workers} workers"
        )

        # Create tool metrics collector (only if show_metrics is True)
        metrics_collector = ToolMetricsCollector() if show_metrics else None

        # Create progress bar
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=self.console,
        )

        # Run validation with Live display showing both progress and metrics
        samples: List[SampleResult] = []

        with Live(
            console=self.console,
            refresh_per_second=2,
        ) as live:
            task = progress.add_task("[cyan]Validating samples...", total=len(papers))

            # Update display function
            def update_display():
                # Combine progress and metrics table (only if metrics collector exists)
                if metrics_collector:
                    metrics_table = metrics_collector.get_stats_table()
                    group = Group(
                        progress,
                        metrics_table
                        if metrics_collector.get_summary()["total_calls"] > 0
                        else "",
                    )
                else:
                    group = progress
                live.update(group)

            # Set callback for metrics updates (only if metrics collector exists)
            if metrics_collector:
                metrics_collector._on_update = update_display

            semaphore = asyncio.Semaphore(max_workers)

            async def validate_sample(paper: Paper) -> SampleResult:
                # Local import to avoid circular dependency
                from src.core.detector import ValidationResult

                ground_truth_type = self._get_ground_truth_type(paper)
                sample_start = time.time()

                logger.info(f"[Benchmark] Starting validation: {paper.title[:50]}...")

                try:
                    prediction = await self.detector.acheck_reference(paper)
                    # Ensure prediction has hallucination_type
                    if not hasattr(prediction, 'hallucination_type') or not prediction.hallucination_type:
                        # Derive from is_hallucination if needed
                        prediction.hallucination_type = "Fabrication" if prediction.is_hallucination else "Real"
                except Exception as e:
                    logger.error(f"[Benchmark] Error validating {paper.title}: {e}")
                    # Treat errors as hallucination detection failures
                    prediction = ValidationResult(
                        hallucination_type="Fabrication",
                        confidence=0.0,
                        reasoning=f"Validation error: {e}",
                        evidence=[],
                    )

                elapsed = time.time() - sample_start
                correct = prediction.hallucination_type == ground_truth_type

                logger.info(
                    f"[Benchmark] Completed: {paper.title[:40]}... "
                    f"({elapsed:.1f}s, correct={correct}, pred={prediction.hallucination_type}, gt={ground_truth_type})"
                )

                progress.update(task, advance=1)
                update_display()

                return SampleResult(
                    paper=paper,
                    prediction=prediction,
                    ground_truth_type=ground_truth_type,
                    correct=correct,
                )

            async def sem_task(paper: Paper) -> SampleResult:
                async with semaphore:
                    return await validate_sample(paper)

            # Run all validations concurrently with semaphore
            tasks = [sem_task(paper) for paper in papers]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Filter out exceptions
            valid_samples = []
            for s in results:
                if isinstance(s, Exception):
                    logger.error(f"Sample validation failed: {s}")
                else:
                    valid_samples.append(s)
            samples = valid_samples

        duration = time.time() - start_time

        # Calculate multi-class metrics
        predicted_types = [s.prediction.hallucination_type for s in samples]
        ground_truth_types = [s.ground_truth_type for s in samples]
        overall_metrics = _calculate_multiclass_metrics(predicted_types, ground_truth_types)

        # Calculate per-type metrics
        per_type_results: dict[str, MultiClassMetrics] = {}
        for htype in ['Real', 'Fabrication', 'AttributionError', 'Irrelevance', 'Counterfactual']:
            type_samples = [s for s in samples if s.ground_truth_type == htype]
            if type_samples:
                type_preds = [s.prediction.hallucination_type for s in type_samples]
                type_truth = [s.ground_truth_type for s in type_samples]
                per_type_results[htype] = _calculate_multiclass_metrics(type_preds, type_truth)

        return BenchmarkResult(
            metrics=overall_metrics,
            per_type_metrics=per_type_results,
            samples=samples,
            duration_seconds=duration,
        )
