"""Metrics dataclasses for benchmark results."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List

from src.bench.schema import Paper
from src.core.types import ValidationResult


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
    prediction: ValidationResult  # Forward reference no longer needed
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
