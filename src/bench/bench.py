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
from ..core.logger import logger
from ..core.tool_monitor import ToolMetricsCollector

# TYPE_CHECKING imports to avoid circular imports
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..core.detector import HallucinationDetector, ValidationResult


@dataclass
class MultiClassMetrics:
    """Multi-class classification metrics for hallucination type detection."""

    # Confusion matrix (actual class -> predicted class -> count)
    confusion_matrix: Dict[str, Dict[str, int]] = field(default_factory=dict)

    # Per-class Precision/Recall/F1
    per_class_precision: Dict[str, float] = field(default_factory=dict)
    per_class_recall: Dict[str, float] = field(default_factory=dict)
    per_class_f1: Dict[str, float] = field(default_factory=dict)
    per_class_support: Dict[str, int] = field(default_factory=dict)

    # Macro Average - each class equally important
    macro_precision: float = 0.0
    macro_recall: float = 0.0
    macro_f1: float = 0.0

    # Micro Average - each sample equally important
    micro_precision: float = 0.0
    micro_recall: float = 0.0
    micro_f1: float = 0.0

    # Weighted Average - weighted by class sample count
    weighted_precision: float = 0.0
    weighted_recall: float = 0.0
    weighted_f1: float = 0.0

    # Overall accuracy
    accuracy: float = 0.0
    total_samples: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "confusion_matrix": self.confusion_matrix,
            "per_class_precision": self.per_class_precision,
            "per_class_recall": self.per_class_recall,
            "per_class_f1": self.per_class_f1,
            "per_class_support": self.per_class_support,
            "macro_precision": self.macro_precision,
            "macro_recall": self.macro_recall,
            "macro_f1": self.macro_f1,
            "micro_precision": self.micro_precision,
            "micro_recall": self.micro_recall,
            "micro_f1": self.micro_f1,
            "weighted_precision": self.weighted_precision,
            "weighted_recall": self.weighted_recall,
            "weighted_f1": self.weighted_f1,
            "accuracy": self.accuracy,
            "total_samples": self.total_samples,
        }


@dataclass
class SampleResult:
    """Result for a single sample."""

    paper: Paper
    prediction: "ValidationResult"  # Forward reference to avoid circular import
    ground_truth_type: str  # e.g., "Real", "Fabrication", "AttributionError", etc.
    correct: bool  # prediction.hallucination_type == ground_truth_type


@dataclass
class BenchmarkResult:
    """Complete benchmark results."""

    metrics: MultiClassMetrics  # Multi-class metrics
    per_type_metrics: Dict[str, MultiClassMetrics]  # Per-class metrics
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
                    "ground_truth_type": s.ground_truth_type,
                    "correct": s.correct,
                }
                for s in self.samples
            ],
        }


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

    def _calculate_multiclass_metrics(
        self,
        predicted_types: List[str],
        ground_truth_types: List[str]
    ) -> MultiClassMetrics:
        """
        Calculate multi-class metrics (Macro/Micro/Weighted Average).

        Classes: ['Real', 'Fabrication', 'AttributionError', 'Irrelevance', 'Counterfactual']
        """
        classes = ['Real', 'Fabrication', 'AttributionError', 'Irrelevance', 'Counterfactual']

        # Build confusion matrix
        confusion = {c: {c2: 0 for c2 in classes} for c in classes}
        for pred, true in zip(predicted_types, ground_truth_types):
            # Handle unknown classes
            if pred not in classes:
                pred = "Fabrication"  # Default fallback
            if true not in classes:
                true = "Real"  # Default fallback
            confusion[true][pred] += 1

        # Calculate per-class Precision, Recall, F1
        per_class_precision = {}
        per_class_recall = {}
        per_class_f1 = {}
        per_class_support = {}

        for c in classes:
            tp = confusion[c][c]  # True positives
            fp = sum(confusion[other][c] for other in classes if other != c)  # False positives
            fn = sum(confusion[c][other] for other in classes if other != c)  # False negatives
            support = sum(confusion[c].values())  # Actual samples for this class

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

            per_class_precision[c] = precision
            per_class_recall[c] = recall
            per_class_f1[c] = f1
            per_class_support[c] = support

        # Calculate Macro Average (simple average)
        macro_precision = sum(per_class_precision.values()) / len(classes)
        macro_recall = sum(per_class_recall.values()) / len(classes)
        macro_f1 = sum(per_class_f1.values()) / len(classes)

        # Calculate Micro Average (based on total TP/FP/FN)
        total_tp = sum(confusion[c][c] for c in classes)
        total_fp = sum(sum(confusion[true][pred] for true in classes if true != pred) for pred in classes)
        total_fn = sum(sum(confusion[true][pred] for pred in classes if pred != true) for true in classes)

        micro_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
        micro_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
        micro_f1 = 2 * micro_precision * micro_recall / (micro_precision + micro_recall) if (micro_precision + micro_recall) > 0 else 0.0

        # Calculate Weighted Average (weighted by support)
        total = sum(per_class_support.values())
        weighted_precision = sum(per_class_precision[c] * per_class_support[c] for c in classes) / total if total > 0 else 0.0
        weighted_recall = sum(per_class_recall[c] * per_class_support[c] for c in classes) / total if total > 0 else 0.0
        weighted_f1 = sum(per_class_f1[c] * per_class_support[c] for c in classes) / total if total > 0 else 0.0

        # Overall accuracy
        accuracy = total_tp / total if total > 0 else 0.0

        return MultiClassMetrics(
            confusion_matrix=confusion,
            per_class_precision=per_class_precision,
            per_class_recall=per_class_recall,
            per_class_f1=per_class_f1,
            per_class_support=per_class_support,
            macro_precision=macro_precision,
            macro_recall=macro_recall,
            macro_f1=macro_f1,
            micro_precision=micro_precision,
            micro_recall=micro_recall,
            micro_f1=micro_f1,
            weighted_precision=weighted_precision,
            weighted_recall=weighted_recall,
            weighted_f1=weighted_f1,
            accuracy=accuracy,
            total_samples=total,
        )

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
                from ..core.detector import ValidationResult

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

        # Calculate multi-class metrics
        predicted_types = [s.prediction.hallucination_type for s in samples]
        ground_truth_types = [s.ground_truth_type for s in samples]
        overall_metrics = self._calculate_multiclass_metrics(predicted_types, ground_truth_types)

        # Calculate per-type metrics
        per_type_results: Dict[str, MultiClassMetrics] = {}
        for htype in ['Real', 'Fabrication', 'AttributionError', 'Irrelevance', 'Counterfactual']:
            type_samples = [s for s in samples if s.ground_truth_type == htype]
            if type_samples:
                type_preds = [s.prediction.hallucination_type for s in type_samples]
                type_truth = [s.ground_truth_type for s in type_samples]
                per_type_results[htype] = self._calculate_multiclass_metrics(type_preds, type_truth)

        return BenchmarkResult(
            metrics=overall_metrics,
            per_type_metrics=per_type_results,
            samples=samples,
            duration_seconds=duration,
        )

    def print_results(self, result: BenchmarkResult):
        """Print benchmark results in a formatted table."""
        self.console.print("\n[bold]Benchmark Results[/bold]\n")

        # Per-class metrics table
        mc = result.metrics
        class_table = Table(
            title="Per-Class Metrics",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta",
        )
        class_table.add_column("Class", style="cyan")
        class_table.add_column("Precision", justify="right")
        class_table.add_column("Recall", justify="right")
        class_table.add_column("F1", justify="right")
        class_table.add_column("Support", justify="right")

        for c in ['Real', 'Fabrication', 'AttributionError', 'Irrelevance', 'Counterfactual']:
            style = "green" if c == "Real" else "yellow"
            support = mc.per_class_support.get(c, 0)
            if support > 0:  # Only show classes that appear in the dataset
                class_table.add_row(
                    f"[{style}]{c}[/{style}]",
                    f"{mc.per_class_precision.get(c, 0):.4f}",
                    f"{mc.per_class_recall.get(c, 0):.4f}",
                    f"{mc.per_class_f1.get(c, 0):.4f}",
                    str(support),
                )

        self.console.print(class_table)
        self.console.print()

        # Confusion matrix table
        cm = mc.confusion_matrix
        confusion_table = Table(
            title="Confusion Matrix (Ground Truth → Predicted)",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta",
        )
        confusion_table.add_column("GT \\ Pred", style="cyan")
        for c in ['Real', 'Fabrication', 'AttributionError', 'Irrelevance', 'Counterfactual']:
            confusion_table.add_column(c[:8], justify="right")  # Shortened names for display

        for true_c in ['Real', 'Fabrication', 'AttributionError', 'Irrelevance', 'Counterfactual']:
            row = [f"[bold]{true_c[:8]}[/bold]"]
            for pred_c in ['Real', 'Fabrication', 'AttributionError', 'Irrelevance', 'Counterfactual']:
                count = cm.get(true_c, {}).get(pred_c, 0)
                # Highlight diagonal (correct predictions)
                if true_c == pred_c:
                    row.append(f"[green]{count}[/green]" if count > 0 else "0")
                else:
                    row.append(f"[red]{count}[/red]" if count > 0 else "0")
            confusion_table.add_row(*row)

        self.console.print(confusion_table)
        self.console.print()

        # Average metrics summary
        avg_table = Table(
            title="Average Metrics",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta",
        )
        avg_table.add_column("Average Type", style="cyan")
        avg_table.add_column("Precision", justify="right")
        avg_table.add_column("Recall", justify="right")
        avg_table.add_column("F1", justify="right")
        avg_table.add_column("Accuracy", justify="right")

        avg_table.add_row(
            "Macro",
            f"{mc.macro_precision:.4f}",
            f"{mc.macro_recall:.4f}",
            f"{mc.macro_f1:.4f}",
            "-"
        )
        avg_table.add_row(
            "Micro",
            f"{mc.micro_precision:.4f}",
            f"{mc.micro_recall:.4f}",
            f"{mc.micro_f1:.4f}",
            f"{mc.accuracy:.4f}"
        )
        avg_table.add_row(
            "Weighted",
            f"{mc.weighted_precision:.4f}",
            f"{mc.weighted_recall:.4f}",
            f"{mc.weighted_f1:.4f}",
            "-"
        )

        self.console.print(avg_table)
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
