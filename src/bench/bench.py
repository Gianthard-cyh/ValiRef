"""
Benchmark module for ValiRef.

.. deprecated::
    This module is kept for backward compatibility.
    Please use the specific submodules instead:
    - `src.bench.runner` for BenchmarkRunner
    - `src.bench.reporter` for print_results
    - `src.bench.metrics` for metrics classes
"""
# Re-export everything for backward compatibility
from src.bench.metrics import (
    BenchmarkResult,
    MultiClassMetrics,
    SampleResult,
    _calculate_multiclass_metrics,
)
from src.bench.reporter import BenchmarkReporter, print_results
from src.bench.runner import BenchmarkRunner

__all__ = [
    "BenchmarkRunner",
    "BenchmarkReporter",
    "BenchmarkResult",
    "MultiClassMetrics",
    "SampleResult",
    "print_results",
    "_calculate_multiclass_metrics",
]
