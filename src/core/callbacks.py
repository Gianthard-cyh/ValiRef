from typing import List, Dict, Any
from abc import ABC
from ..bench.schema import Paper, Reference
from .state import PipelineState


class ValidationCallback(ABC):
    """Base class for validation pipeline callbacks."""

    async def on_pipeline_start(self, filename: str):
        """Called when the pipeline starts processing a file."""
        pass

    async def on_extraction_start(self, filename: str):
        """Called when reference extraction starts."""
        pass

    async def on_extraction_end(self, references: List[Paper]):
        """Called when reference extraction completes."""
        pass

    async def on_validation_start(self, total_references: int):
        """Called when validation of references starts."""
        pass

    async def on_reference_validation_start(self, paper: Paper, index: int, total: int):
        """Called before validating a single reference."""
        pass

    async def on_reference_validation_end(self, paper: Paper, result: Dict[str, Any]):
        """Called after validating a single reference."""
        pass

    async def on_reference_validation_error(self, paper: Paper, error: Exception):
        """Called when validation fails for a reference."""
        pass

    async def on_pipeline_end(self, results: Dict[str, Any]):
        """Called when the pipeline completes."""
        pass

    async def on_error(self, error: Exception):
        """Called when a critical pipeline error occurs."""
        pass

    async def on_phase_change(self, state: PipelineState):
        """Called when pipeline phase changes."""
        pass

    async def on_extraction_progress(self, state: PipelineState, new_refs: List[Reference]):
        """Called during streaming extraction when new references are found."""
        pass
