from typing import List, Dict, Any
from abc import ABC
from ..bench.schema import Paper


class ValidationCallback(ABC):
    """Base class for validation pipeline callbacks."""

    def on_pipeline_start(self, filename: str):
        """Called when the pipeline starts processing a file."""
        pass

    def on_extraction_start(self, filename: str):
        """Called when reference extraction starts."""
        pass

    def on_extraction_end(self, references: List[Paper]):
        """Called when reference extraction completes."""
        pass

    def on_validation_start(self, total_references: int):
        """Called when validation of references starts."""
        pass

    def on_reference_validation_start(self, paper: Paper, index: int, total: int):
        """Called before validating a single reference."""
        pass

    def on_reference_validation_end(self, paper: Paper, result: Dict[str, Any]):
        """Called after validating a single reference."""
        pass

    def on_reference_validation_error(self, paper: Paper, error: Exception):
        """Called when validation fails for a reference."""
        pass

    def on_pipeline_end(self, results: Dict[str, Any]):
        """Called when the pipeline completes."""
        pass

    def on_error(self, error: Exception):
        """Called when a critical pipeline error occurs."""
        pass
