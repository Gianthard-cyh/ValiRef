"""Metrics calculation functions."""
from typing import List

from src.bench.metrics.dataclasses import MultiClassMetrics


def _calculate_multiclass_metrics(
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
