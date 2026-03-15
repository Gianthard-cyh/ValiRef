"""Hallucination models for structured LLM output."""
from typing import List

from pydantic import BaseModel, Field


class FakePaper(BaseModel):
    title: str = Field(description="The title of the fake paper")
    abstract: str = Field(description="The abstract of the fake paper")
    authors: List[str] = Field(
        description="List of plausible authors for the fake paper"
    )
    published_date: str = Field(description="A plausible publication date (YYYY-MM-DD)")


class FakeAuthors(BaseModel):
    authors: List[str] = Field(
        description="List of plausible but incorrect authors for this paper"
    )


class IrrelevantContext(BaseModel):
    context: str = Field(
        description="A paragraph that cites the paper to support a specific claim"
    )


class CounterfactualClaim(BaseModel):
    context: str = Field(
        description="A citation paragraph claiming the opposite of the paper's actual findings"
    )
