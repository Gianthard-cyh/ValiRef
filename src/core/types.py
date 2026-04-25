"""Core shared types to avoid circular imports."""

from typing import List
from pydantic import BaseModel, Field


class ValidationResult(BaseModel):
    """Result from hallucination detection validation."""

    hallucination_type: str = Field(
        description="Category: 'Real', 'Fabrication', 'AttributionError', 'Irrelevance', or 'Counterfactual'"
    )
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")
    reasoning: str = Field(description="Explanation for the judgment")
    evidence: List[str] = Field(
        default_factory=list,
        description="URLs found that support the judgment",
    )

    # Computed property for backward compatibility
    @property
    def is_hallucination(self) -> bool:
        return self.hallucination_type != "Real"
