from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List
from ..bench.schema import Reference


class ValidationPhase(Enum):
    IDLE = "idle"
    EXTRACTION = "extraction"
    DETECTION = "detection"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class PipelineState:
    """Pipeline execution state for real-time progress tracking."""

    phase: ValidationPhase = ValidationPhase.IDLE
    current_file: Optional[str] = None
    extraction_found: int = 0
    detection_total: int = 0
    detection_processed: int = 0
    current_reference: Optional[str] = None
    error: Optional[str] = None
    extracted_refs: List[Reference] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "phase": self.phase.value,
            "current_file": self.current_file,
            "extraction_found": self.extraction_found,
            "detection_total": self.detection_total,
            "detection_processed": self.detection_processed,
            "current_reference": self.current_reference,
            "error": self.error,
        }
