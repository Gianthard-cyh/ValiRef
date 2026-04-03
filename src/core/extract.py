from abc import ABC, abstractmethod
from typing import List, Optional
import fitz  # pymupdf
from langchain_deepseek import ChatDeepSeek
from langchain_core.prompts import ChatPromptTemplate

from ..bench.schema import Paper, ReferenceList
from .config import (
    DEEPSEEK_API_KEY,
    LLM_MODEL,
    LLM_TEMPERATURE,
    LLM_MAX_TOKENS,
    LLM_TIMEOUT,
    LLM_MAX_RETRIES,
    EXTRACTION_CHAR_LIMIT,
)
from .logger import logger
from .exceptions import ExtractionError, ErrorCode

"""
Extract structured information from the input
"""


class Extractor(ABC):
    """
    Abstract base class for extractors
    """

    @abstractmethod
    async def extract(self, *args) -> List[Paper]:
        """
        Extract a list of referenced papers from the input
        """
        raise NotImplementedError

    @abstractmethod
    async def extract_batch(self, *args) -> List[List[Paper]]:
        """
        Extract lists of referenced papers from a batch of inputs
        """
        raise NotImplementedError


class TextExtractor(Extractor):
    def __init__(self, llm: Optional[ChatDeepSeek] = None):
        if llm is not None:
            self.model = llm
        else:
            if DEEPSEEK_API_KEY is None:
                raise ValueError("DEEPSEEK_API_KEY is not set")

            self.model = ChatDeepSeek(
                model=LLM_MODEL,
                temperature=LLM_TEMPERATURE,
                max_tokens=LLM_MAX_TOKENS,
                timeout=LLM_TIMEOUT,
                max_retries=LLM_MAX_RETRIES,
                api_key=DEEPSEEK_API_KEY,
            )

    async def extract(self, text: str) -> List[Paper]:
        """
        Extract a list of referenced papers from a text string
        """
        # Validate input text
        if not text or not text.strip():
            raise ExtractionError(
                message="PDF contains no text content (possibly a scanned image PDF)",
                error_code=ErrorCode.PDF_NO_TEXT
            )

        stripped_text = text.strip()
        if len(stripped_text) < 500:
            raise ExtractionError(
                message=f"PDF text too short ({len(stripped_text)} chars), cannot extract references",
                error_code=ErrorCode.PDF_TOO_SHORT
            )

        prompt = ChatPromptTemplate.from_template(
            "You are an expert researcher. Extract a list of referenced/cited research papers from the following text segment.\n"
            "The text is the END of a research paper, containing the References/Bibliography section.\n"
            "Extract as many references as possible into the ReferenceList schema.\n"
            "For each reference, extract Title, Authors, Date, ArXiv ID (if present), and Venue/Journal (e.g., 'NeurIPS', 'ICLR', 'Nature').\n"
            "If a field is missing, infer or use 'N/A'.\n"
            "\n"
            "Text Segment:\n{text}"
        )

        # Smart truncation: Look for "References" or "Bibliography"
        truncated_text = text[-EXTRACTION_CHAR_LIMIT:]  # Default fallback

        # Search from the end backwards to find the last occurrence (usually the section header)
        # Check common headers
        headers = ["References", "Bibliography", "REFERENCES", "BIBLIOGRAPHY"]
        found_pos = -1

        for header in headers:
            # Search in the last 50% of text to avoid finding it in Table of Contents or Intro
            search_start = len(text) // 2
            pos = text.rfind(header, search_start)
            if pos != -1:
                if found_pos == -1 or pos > found_pos:
                    found_pos = pos

        if found_pos != -1:
            # Take from the header to the end
            # Also include a bit of context before just in case
            start_pos = max(0, found_pos)
            truncated_text = text[start_pos:]

            # If the resulting text is still too long, truncate it
            if len(truncated_text) > EXTRACTION_CHAR_LIMIT:
                truncated_text = truncated_text[:EXTRACTION_CHAR_LIMIT]
        else:
            # Fallback to last N chars
            truncated_text = text[-EXTRACTION_CHAR_LIMIT:]

        structured_llm = self.model.with_structured_output(ReferenceList)
        chain = prompt | structured_llm

        result = await chain.ainvoke({"text": truncated_text})

        if result is None:
            raise ExtractionError(
                message="LLM extraction returned None. The references might be outside the truncated text window.",
                error_code=ErrorCode.EXTRACTION_FAILED
            )

        if not result.references:
            raise ExtractionError(
                message="No references found in the PDF. The document might not contain a references section, or it might be in an unsupported format.",
                error_code=ErrorCode.NO_REFERENCES_FOUND
            )

        papers = []
        for ref in result.references:
            # Convert Reference to Paper
            paper = Paper(
                source="reference",
                id=ref.arxiv_id if ref.arxiv_id else "N/A",
                title=ref.title,
                abstract="N/A",
                authors=ref.authors,
                published_date=ref.date,
                url=f"https://arxiv.org/abs/{ref.arxiv_id}" if ref.arxiv_id else "N/A",
                pdf_url=f"https://arxiv.org/pdf/{ref.arxiv_id}.pdf"
                if ref.arxiv_id
                else None,
                venue=ref.venue,
            )
            papers.append(paper)

        return papers

    async def extract_batch(self, texts: List[str]) -> List[List[Paper]]:
        """Extract lists of referenced papers from a batch of text strings."""
        results = []
        for text in texts:
            results.append(await self.extract(text))
        return results


class PDFExtractor(Extractor):
    def __init__(self, text_extractor: Optional[TextExtractor] = None):
        self.text_extractor = (
            text_extractor if text_extractor is not None else TextExtractor()
        )

    async def extract(self, file_path: str) -> List[Paper]:
        """
        Extract a list of referenced papers from a PDF file path
        """
        try:
            doc = fitz.open(file_path)
        except Exception as e:
            raise ExtractionError(
                message=f"Failed to open PDF file: {str(e)}",
                error_code=ErrorCode.PDF_CORRUPTED
            ) from e

        text = ""
        for page in doc:
            text += page.get_text()

        return await self.text_extractor.extract(text)

    async def extract_batch(self, file_paths: List[str]) -> List[List[Paper]]:
        """Extract lists of referenced papers from a batch of PDF file paths."""
        results = []
        for file_path in file_paths:
            results.append(await self.extract(file_path))
        return results
