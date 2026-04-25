"""Bench module for ValiRef."""
from src.bench.bench import (
    BenchmarkResult,
    BenchmarkRunner,
    MultiClassMetrics,
    SampleResult,
    print_results,
)
from src.bench.dataset.dataset import BenchmarkDataset
from src.bench.factory import BenchmarkDatasetFactory
from src.bench.reporter import BenchmarkReporter
from src.bench.schema import Paper, PaperList, Reference, ReferenceList

__all__ = [
    # Schema
    "Paper",
    "PaperList",
    "Reference",
    "ReferenceList",
    # Dataset
    "BenchmarkDataset",
    "BenchmarkDatasetFactory",
    # Runner & Results
    "BenchmarkRunner",
    "BenchmarkReporter",
    "BenchmarkResult",
    "MultiClassMetrics",
    "SampleResult",
    "print_results",
]
