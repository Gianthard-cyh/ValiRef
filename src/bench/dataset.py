"""
Benchmark dataset module.

.. deprecated::
    This module is kept for backward compatibility.
    Please use the specific submodules instead:
    - `src.bench.dataset` for BenchmarkDataset
    - `src.bench.factory` for BenchmarkDatasetFactory
    - `src.bench.models` for hallucination models
"""
# Re-export everything for backward compatibility
from src.bench.dataset.dataset import BenchmarkDataset
from src.bench.factory import BenchmarkDatasetFactory
from src.bench.models.hallucination import (
    CounterfactualClaim,
    FakeAuthors,
    FakePaper,
    IrrelevantContext,
)

__all__ = [
    "BenchmarkDataset",
    "BenchmarkDatasetFactory",
    "FakePaper",
    "FakeAuthors",
    "IrrelevantContext",
    "CounterfactualClaim",
]
