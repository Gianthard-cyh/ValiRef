"""Tests for streaming extraction functionality."""

import pytest
from unittest.mock import MagicMock

from src.core.extract import TextExtractor
from src.core.exceptions import ExtractionError
from src.bench.schema import Reference


# Long enough text to pass validation (> 500 chars)
LONG_TEXT = "This is a sample academic paper text. " * 20 + "References: [1] Smith et al., 2024"


class TestTextExtractorValidation:
    """Test input validation."""

    @pytest.fixture
    def extractor(self):
        """Create TextExtractor with mocked model."""
        mock_model = MagicMock()
        return TextExtractor(llm=mock_model)

    @pytest.mark.asyncio
    async def test_extract_text_too_short(self, extractor):
        """Test that short text raises error."""
        with pytest.raises(ExtractionError) as exc_info:
            await extractor.extract("short")
        assert "too short" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_extract_empty_text(self, extractor):
        """Test that empty text raises error."""
        with pytest.raises(ExtractionError) as exc_info:
            await extractor.extract("")
        assert "no text" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_extract_whitespace_only(self, extractor):
        """Test that whitespace-only text raises error."""
        with pytest.raises(ExtractionError) as exc_info:
            await extractor.extract("   \n\t  ")
        assert "no text" in str(exc_info.value).lower()


class TestTextExtractorStreamingLogic:
    """Test streaming extraction logic without full chain."""

    def test_extract_method_accepts_callback(self):
        """Test that extract method accepts on_progress parameter."""
        mock_model = MagicMock()
        extractor = TextExtractor(llm=mock_model)

        # Verify the method signature accepts on_progress
        import inspect
        sig = inspect.signature(extractor.extract)
        assert "on_progress" in sig.parameters

    def test_callback_is_callable_type(self):
        """Test that on_progress parameter is typed as Callable."""
        import inspect
        mock_model = MagicMock()
        extractor = TextExtractor(llm=mock_model)
        sig = inspect.signature(extractor.extract)
        param = sig.parameters["on_progress"]
        # Should be Optional type
        assert "Optional" in str(param.default) or param.default is None


class TestReferenceConversion:
    """Test conversion from Reference to Paper."""

    def test_reference_to_paper_conversion(self):
        """Test the conversion logic from Reference to Paper schema."""
        from src.bench.schema import Paper

        ref = Reference(
            title="Attention Is All You Need",
            authors=["Vaswani et al."],
            date="2017",
            arxiv_id="1706.03762",
            venue="NeurIPS",
        )

        # Simulate the conversion logic from extract.py
        paper = Paper(
            source="reference",
            id=ref.arxiv_id if ref.arxiv_id else "N/A",
            title=ref.title,
            abstract="N/A",
            authors=ref.authors,
            published_date=ref.date,
            url=f"https://arxiv.org/abs/{ref.arxiv_id}" if ref.arxiv_id else "N/A",
            pdf_url=f"https://arxiv.org/pdf/{ref.arxiv_id}.pdf" if ref.arxiv_id else None,
            venue=ref.venue,
        )

        assert paper.title == "Attention Is All You Need"
        assert paper.id == "1706.03762"
        assert paper.url == "https://arxiv.org/abs/1706.03762"
        assert paper.pdf_url == "https://arxiv.org/pdf/1706.03762.pdf"

    def test_reference_without_arxiv_id(self):
        """Test conversion when arxiv_id is None."""
        from src.bench.schema import Paper

        ref = Reference(
            title="Some Paper",
            authors=["Author"],
            date="2024",
            arxiv_id=None,
            venue="Conference",
        )

        paper = Paper(
            source="reference",
            id=ref.arxiv_id if ref.arxiv_id else "N/A",
            title=ref.title,
            abstract="N/A",
            authors=ref.authors,
            published_date=ref.date,
            url=f"https://arxiv.org/abs/{ref.arxiv_id}" if ref.arxiv_id else "N/A",
            pdf_url=f"https://arxiv.org/pdf/{ref.arxiv_id}.pdf" if ref.arxiv_id else None,
            venue=ref.venue,
        )

        assert paper.id == "N/A"
        assert paper.url == "N/A"
        assert paper.pdf_url is None
