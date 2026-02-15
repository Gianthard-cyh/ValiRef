from typing import List, Optional
from pydantic import BaseModel, Field

class Paper(BaseModel):
    """
    Schema representing a research paper.
    """
    source: str = Field(..., description="Source of the paper (e.g., 'arxiv')")
    id: str = Field(..., description="Unique identifier of the paper")
    title: str = Field(..., description="Title of the paper")
    abstract: str = Field(..., description="Abstract of the paper")
    authors: List[str] = Field(default_factory=list, description="List of authors")
    published_date: str = Field(..., description="Publication date")
    updated_date: Optional[str] = Field(None, description="Last update date")
    url: str = Field(..., description="URL to the paper page")
    pdf_url: Optional[str] = Field(None, description="URL to the PDF file")
    claims: List[str] = Field(default_factory=list, description="List of extracted claims")
    hallucination_type: Optional[str] = Field(None, description="Type of injected hallucination")
    original_paper_id: Optional[str] = Field(None, description="ID of the original paper if hallucinated")
    venue: Optional[str] = Field(None, description="Venue or Journal where the paper was published")

class PaperList(BaseModel):
    """
    A list of research papers.
    """
    papers: List[Paper] = Field(default_factory=list, description="List of extracted papers")

class Reference(BaseModel):
    """
    Schema representing a cited reference.
    """
    title: str = Field(description="Title of the cited paper")
    authors: List[str] = Field(default_factory=list, description="List of authors")
    date: str = Field(description="Publication date or year")
    arxiv_id: Optional[str] = Field(None, description="ArXiv ID if available")
    venue: Optional[str] = Field(None, description="Venue or Journal where the paper was published")

class ReferenceList(BaseModel):
    """
    A list of references.
    """
    references: List[Reference] = Field(default_factory=list, description="List of extracted references")
