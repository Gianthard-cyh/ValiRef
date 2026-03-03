import csv
import asyncio
import random
import time
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeRemainingColumn,
)
from rich.console import Console, Group
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich import box

from .schema import Paper
from ..core.detector import HallucinationDetector, ValidationResult
from ..core.logger import logger
from ..core.tool_monitor import ToolMetricsCollector


@dataclass
class Metrics:
    """Evaluation metrics for benchmark results."""
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    total_samples: int = 0
    true_positives: int = 0
    true_negatives: int = 0
    false_positives: int = 0
    false_negatives: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "accuracy": self.accuracy,
            "precision": self.precision,
            "recall": self.recall,
            "f1_score": self.f1_score,
            "total_samples": self.total_samples,
            "true_positives": self.true_positives,
            "true_negatives": self.true_negatives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
        }


@dataclass
class SampleResult:
    """Result for a single sample."""
    paper: Paper
    prediction: ValidationResult
    ground_truth: bool  # True if hallucinated, False if real
    correct: bool


@dataclass
class BenchmarkResult:
    """Complete benchmark results."""
    metrics: Metrics
    per_type_metrics: Dict[str, Metrics]
    samples: List[SampleResult]
    duration_seconds: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "duration_seconds": self.duration_seconds,
            "metrics": self.metrics.to_dict(),
            "per_type_metrics": {
                htype: m.to_dict() for htype, m in self.per_type_metrics.items()
            },
            "samples": [
                {
                    "paper": s.paper.model_dump(),
                    "prediction": s.prediction.model_dump(),
                    "ground_truth": s.ground_truth,
                    "correct": s.correct,
                }
                for s in self.samples
            ],
        }


class BenchmarkRunner:
    """Runner for benchmarking hallucination detection performance."""

    def __init__(self, detector: HallucinationDetector):
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

    def _is_hallucinated(self, paper: Paper) -> bool:
        """Determine if a paper is hallucinated based on its type."""
        # Real papers have no hallucination_type or it's empty/None
        if not paper.hallucination_type:
            return False
        # Any non-empty hallucination_type means it's a hallucinated sample
        return True

    def _calculate_metrics(
        self, predictions: List[bool], ground_truth: List[bool]
    ) -> Metrics:
        """Calculate evaluation metrics from predictions and ground truth."""
        if len(predictions) != len(ground_truth):
            raise ValueError("Predictions and ground truth must have same length")

        tp = sum(1 for p, g in zip(predictions, ground_truth) if p and g)
        tn = sum(1 for p, g in zip(predictions, ground_truth) if not p and not g)
        fp = sum(1 for p, g in zip(predictions, ground_truth) if p and not g)
        fn = sum(1 for p, g in zip(predictions, ground_truth) if not p and g)

        total = len(predictions)
        accuracy = (tp + tn) / total if total > 0 else 0.0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (
            2 * (precision * recall) / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )

        return Metrics(
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            f1_score=f1,
            total_samples=total,
            true_positives=tp,
            true_negatives=tn,
            false_positives=fp,
            false_negatives=fn,
        )

    async def run(
        self,
        dataset_path: str,
        max_workers: int = 5,
        limit: Optional[int] = None,
        verbose: bool = False,
    ) -> BenchmarkResult:
        """
        Run benchmark on the dataset.

        Args:
            dataset_path: Path to the CSV dataset file
            max_workers: Number of concurrent validation workers
            limit: Optional limit on number of samples to test
            verbose: Enable verbose output

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

        # Create tool metrics collector
        metrics_collector = ToolMetricsCollector()

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
                # Combine progress and metrics table
                metrics_table = metrics_collector.get_stats_table()
                group = Group(
                    progress,
                    metrics_table if metrics_collector.get_summary()["total_calls"] > 0 else ""
                )
                live.update(group)

            # Set callback for metrics updates
            metrics_collector._on_update = update_display

            semaphore = asyncio.Semaphore(max_workers)

            async def validate_sample(paper: Paper) -> SampleResult:
                ground_truth = self._is_hallucinated(paper)
                sample_start = time.time()

                logger.info(f"[Benchmark] Starting validation: {paper.title[:50]}...")

                try:
                    prediction = await self.detector.acheck_reference(paper)
                    predicted_hallucination = prediction.is_hallucination
                except Exception as e:
                    logger.error(f"[Benchmark] Error validating {paper.title}: {e}")
                    # Treat errors as hallucination detection failures
                    prediction = ValidationResult(
                        is_hallucination=True,
                        confidence=0.0,
                        reasoning=f"Validation error: {e}",
                        evidence=[],
                    )
                    predicted_hallucination = True

                elapsed = time.time() - sample_start
                correct = predicted_hallucination == ground_truth

                logger.info(
                    f"[Benchmark] Completed: {paper.title[:40]}... "
                    f"({elapsed:.1f}s, correct={correct})"
                )

                progress.update(task, advance=1)
                update_display()

                return SampleResult(
                    paper=paper,
                    prediction=prediction,
                    ground_truth=ground_truth,
                    correct=correct,
                )

            async def sem_task(paper: Paper) -> SampleResult:
                async with semaphore:
                    return await validate_sample(paper)

            # Run all validations concurrently with semaphore
            tasks = [sem_task(paper) for paper in papers]
            samples = await asyncio.gather(*tasks, return_exceptions=True)

            # Filter out exceptions
            valid_samples = []
            for s in samples:
                if isinstance(s, Exception):
                    logger.error(f"Sample validation failed: {s}")
                else:
                    valid_samples.append(s)
            samples = valid_samples

        duration = time.time() - start_time

        # Calculate overall metrics
        predictions = [s.prediction.is_hallucination for s in samples]
        ground_truths = [s.ground_truth for s in samples]
        overall_metrics = self._calculate_metrics(predictions, ground_truths)

        # Calculate per-type metrics
        per_type_metrics: Dict[str, List[SampleResult]] = {}
        for s in samples:
            htype = s.paper.hallucination_type or "Real"
            if htype not in per_type_metrics:
                per_type_metrics[htype] = []
            per_type_metrics[htype].append(s)

        per_type_results: Dict[str, Metrics] = {}
        for htype, type_samples in per_type_metrics.items():
            type_preds = [s.prediction.is_hallucination for s in type_samples]
            type_truth = [s.ground_truth for s in type_samples]
            per_type_results[htype] = self._calculate_metrics(type_preds, type_truth)

        return BenchmarkResult(
            metrics=overall_metrics,
            per_type_metrics=per_type_results,
            samples=samples,
            duration_seconds=duration,
        )

    def print_results(self, result: BenchmarkResult):
        """Print benchmark results in a formatted table."""
        self.console.print("\n[bold]Benchmark Results[/bold]\n")

        # Overall metrics table
        metrics_table = Table(
            title="Overall Metrics",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta",
        )
        metrics_table.add_column("Metric", style="cyan")
        metrics_table.add_column("Value", justify="right", style="green")

        m = result.metrics
        metrics_table.add_row("Accuracy", f"{m.accuracy:.4f}")
        metrics_table.add_row("Precision", f"{m.precision:.4f}")
        metrics_table.add_row("Recall", f"{m.recall:.4f}")
        metrics_table.add_row("F1 Score", f"{m.f1_score:.4f}")
        metrics_table.add_row("Total Samples", str(m.total_samples))
        metrics_table.add_row("True Positives", str(m.true_positives))
        metrics_table.add_row("True Negatives", str(m.true_negatives))
        metrics_table.add_row("False Positives", str(m.false_positives))
        metrics_table.add_row("False Negatives", str(m.false_negatives))

        self.console.print(metrics_table)
        self.console.print()

        # Per-type metrics table
        if result.per_type_metrics:
            type_table = Table(
                title="Per-Hallucination-Type Metrics",
                box=box.ROUNDED,
                show_header=True,
                header_style="bold magenta",
            )
            type_table.add_column("Type", style="cyan")
            type_table.add_column("Accuracy", justify="right")
            type_table.add_column("Precision", justify="right")
            type_table.add_column("Recall", justify="right")
            type_table.add_column("F1", justify="right")
            type_table.add_column("Count", justify="right")

            for htype, metrics in result.per_type_metrics.items():
                style = "green" if htype == "Real" else "yellow"
                type_table.add_row(
                    f"[{style}]{htype}[/{style}]",
                    f"{metrics.accuracy:.4f}",
                    f"{metrics.precision:.4f}",
                    f"{metrics.recall:.4f}",
                    f"{metrics.f1_score:.4f}",
                    str(metrics.total_samples),
                )

            self.console.print(type_table)
            self.console.print()

        # Summary panel
        correct = sum(1 for s in result.samples if s.correct)
        total = len(result.samples)
        accuracy_pct = (correct / total * 100) if total > 0 else 0

        summary_text = (
            f"Correctly classified: {correct}/{total} ({accuracy_pct:.1f}%)\n"
            f"Duration: {result.duration_seconds:.2f}s\n"
            f"Throughput: {total / result.duration_seconds:.2f} samples/sec"
        )

        self.console.print(
            Panel(
                summary_text,
                title="Summary",
                border_style="blue",
                box=box.ROUNDED,
            )
        )
