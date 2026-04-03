"""
Unit tests for src.core.extract module with dependency injection.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from src.core.extract import TextExtractor, PDFExtractor, Extractor
from src.core.exceptions import ExtractionError, ErrorCode
from src.bench.schema import Paper


class TestTextExtractor:
    """Tests for TextExtractor with dependency injection."""

    @pytest.mark.asyncio
    async def test_constructor_with_mock_llm(self):
        """Test TextExtractor accepts mock LLM via constructor."""
        # Create a mock LLM
        mock_llm = MagicMock()

        # Create extractor with injected LLM
        extractor = TextExtractor(llm=mock_llm)

        assert extractor.model == mock_llm

    @pytest.mark.asyncio
    async def test_extract_empty_text_raises_pdf_no_text(self):
        """Test extract raises ExtractionError with PDF_NO_TEXT for empty text."""
        mock_llm = MagicMock()
        extractor = TextExtractor(llm=mock_llm)

        with pytest.raises(ExtractionError) as exc_info:
            await extractor.extract("")

        assert exc_info.value.error_code == ErrorCode.PDF_NO_TEXT
        assert "no text" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_extract_whitespace_only_raises_pdf_no_text(self):
        """Test extract raises ExtractionError for whitespace-only text."""
        mock_llm = MagicMock()
        extractor = TextExtractor(llm=mock_llm)

        with pytest.raises(ExtractionError) as exc_info:
            await extractor.extract("   \n\t  ")

        assert exc_info.value.error_code == ErrorCode.PDF_NO_TEXT

    @pytest.mark.asyncio
    async def test_extract_short_text_raises_pdf_too_short(self):
        """Test extract raises ExtractionError with PDF_TOO_SHORT for short text."""
        mock_llm = MagicMock()
        extractor = TextExtractor(llm=mock_llm)

        with pytest.raises(ExtractionError) as exc_info:
            await extractor.extract("Short text")  # Less than 500 chars

        assert exc_info.value.error_code == ErrorCode.PDF_TOO_SHORT
        assert "too short" in exc_info.value.message.lower()

    @pytest.mark.asyncio
    async def test_extract_none_result_raises_extraction_failed(self):
        """Test extract raises ExtractionError when LLM returns None."""
        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=None)
        mock_structured.__or__ = MagicMock(return_value=mock_chain)
        mock_llm.with_structured_output.return_value = mock_structured

        extractor = TextExtractor(llm=mock_llm)

        # Mock the prompt chain setup
        from langchain_core.prompts import ChatPromptTemplate

        with patch.object(
            ChatPromptTemplate,
            "from_template",
            return_value=MagicMock(__or__=MagicMock(return_value=mock_chain)),
        ):
            with pytest.raises(ExtractionError) as exc_info:
                await extractor.extract("A" * 1000)  # Valid length text

        assert exc_info.value.error_code == ErrorCode.EXTRACTION_FAILED
        assert "None" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_extract_empty_references_raises_no_references_found(self):
        """Test extract raises ExtractionError when no references found."""
        mock_result = MagicMock()
        mock_result.references = []

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=mock_result)
        mock_structured.__or__ = MagicMock(return_value=mock_chain)
        mock_llm.with_structured_output.return_value = mock_structured

        extractor = TextExtractor(llm=mock_llm)

        from langchain_core.prompts import ChatPromptTemplate

        with patch.object(
            ChatPromptTemplate,
            "from_template",
            return_value=MagicMock(__or__=MagicMock(return_value=mock_chain)),
        ):
            with pytest.raises(ExtractionError) as exc_info:
                await extractor.extract("A" * 1000)

        assert exc_info.value.error_code == ErrorCode.NO_REFERENCES_FOUND

    @pytest.mark.asyncio
    async def test_extract_with_mock_llm(self):
        """Test extract method with mocked LLM."""
        # Setup mock - the chain uses pipe operator
        mock_result = MagicMock()
        mock_result.references = [
            MagicMock(
                title="Test Paper",
                authors=["Author One", "Author Two"],
                date="2023",
                arxiv_id="2301.12345",
                venue="ICLR",
            )
        ]

        # Mock the chain invocation
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=mock_result)

        # Mock the LLM with structured output
        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_llm.with_structured_output.return_value = mock_structured

        # When prompt | structured is called, return mock_chain
        from langchain_core.prompts import ChatPromptTemplate

        with patch.object(
            ChatPromptTemplate,
            "from_template",
            return_value=MagicMock(__or__=MagicMock(return_value=mock_chain)),
        ):
            extractor = TextExtractor(llm=mock_llm)

            # Execute with long enough text
            text = "References\n1. Test Paper by Author One, Author Two (2023)" + "A" * 500
            papers = await extractor.extract(text)

            # Verify
            assert len(papers) == 1
            assert papers[0].title == "Test Paper"
            assert papers[0].authors == ["Author One", "Author Two"]
            assert papers[0].id == "2301.12345"

    @pytest.mark.asyncio
    async def test_extract_batch(self):
        """Test extract_batch with mocked LLM - simplified to verify DI works."""
        # Just verify that extract_batch calls extract for each text
        mock_llm = MagicMock()
        extractor = TextExtractor(llm=mock_llm)

        # Mock the extract method directly
        with patch.object(extractor, "extract", new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = [
                Paper(
                    source="reference",
                    id="123",
                    title="Paper",
                    abstract="Abstract",
                    authors=["Author"],
                    published_date="2023",
                    url="http://example.com",
                )
            ]

            texts = ["Text 1", "Text 2"]
            results = await extractor.extract_batch(texts)

            assert len(results) == 2
            assert mock_extract.call_count == 2


class TestPDFExtractor:
    """Tests for PDFExtractor with dependency injection."""

    @pytest.mark.asyncio
    async def test_constructor_with_mock_text_extractor(self):
        """Test PDFExtractor accepts mock TextExtractor via constructor."""
        mock_text_extractor = MagicMock(spec=TextExtractor)
        extractor = PDFExtractor(text_extractor=mock_text_extractor)

        assert extractor.text_extractor == mock_text_extractor

    @pytest.mark.asyncio
    async def test_extract_corrupted_pdf_raises_pdf_corrupted(self):
        """Test extract raises ExtractionError when PDF cannot be opened."""
        mock_text_extractor = MagicMock(spec=TextExtractor)
        extractor = PDFExtractor(text_extractor=mock_text_extractor)

        with patch("fitz.open", side_effect=Exception("Invalid PDF header")):
            with pytest.raises(ExtractionError) as exc_info:
                await extractor.extract("/path/to/corrupted.pdf")

        assert exc_info.value.error_code == ErrorCode.PDF_CORRUPTED
        assert "Failed to open PDF" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_extract_empty_pdf_raises_pdf_no_text(self):
        """Test extract raises ExtractionError when PDF has no text."""
        mock_text_extractor = MagicMock(spec=TextExtractor)
        mock_text_extractor.extract = AsyncMock(
            side_effect=ExtractionError("PDF contains no text", error_code=ErrorCode.PDF_NO_TEXT)
        )

        extractor = PDFExtractor(text_extractor=mock_text_extractor)

        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = ""  # Empty text
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))

        with patch("fitz.open", return_value=mock_doc):
            with pytest.raises(ExtractionError) as exc_info:
                await extractor.extract("/path/to/empty.pdf")

        assert exc_info.value.error_code == ErrorCode.PDF_NO_TEXT

    @pytest.mark.asyncio
    async def test_extract_delegates_to_text_extractor(self):
        """Test PDF.extract delegates to text_extractor.extract."""
        mock_text_extractor = MagicMock(spec=TextExtractor)
        mock_text_extractor.extract = AsyncMock(
            return_value=[
                Paper(
                    source="reference",
                    id="123",
                    title="Test Paper",
                    abstract="Abstract",
                    authors=["Author"],
                    published_date="2023",
                    url="http://example.com",
                )
            ]
        )

        extractor = PDFExtractor(text_extractor=mock_text_extractor)

        # Mock fitz.open
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = "PDF content"
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))

        with patch("fitz.open", return_value=mock_doc):
            papers = await extractor.extract("/path/to/paper.pdf")

        assert len(papers) == 1
        assert papers[0].title == "Test Paper"
        mock_text_extractor.extract.assert_called_once_with("PDF content")

    @pytest.mark.asyncio
    async def test_extract_batch_delegates_to_extract(self):
        """Test extract_batch handles multiple files."""
        mock_text_extractor = MagicMock(spec=TextExtractor)
        mock_text_extractor.extract = AsyncMock(return_value=[])

        extractor = PDFExtractor(text_extractor=mock_text_extractor)

        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Content"
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))

        with patch("fitz.open", return_value=mock_doc):
            results = await extractor.extract_batch(["/path/1.pdf", "/path/2.pdf"])

        assert len(results) == 2
        assert mock_text_extractor.extract.call_count == 2

    @pytest.mark.asyncio
    async def test_extract_propagates_errors(self):
        """Test extract propagates errors - not silently caught."""
        mock_text_extractor = MagicMock(spec=TextExtractor)
        mock_text_extractor.extract = AsyncMock(
            side_effect=Exception("Extraction error")
        )

        extractor = PDFExtractor(text_extractor=mock_text_extractor)

        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Content"
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))

        with patch("fitz.open", return_value=mock_doc):
            # Errors should propagate, not be silently caught
            with pytest.raises(Exception, match="Extraction error"):
                await extractor.extract_batch(["/path/1.pdf"])


class TestExtractorAbstract:
    """Tests for the abstract Extractor base class."""

    def test_abstract_methods(self):
        """Test that Extractor cannot be instantiated directly."""
        with pytest.raises(TypeError):
            Extractor()

    def test_subclass_must_implement(self):
        """Test that subclasses must implement abstract methods."""

        class IncompleteExtractor(Extractor):
            pass

        with pytest.raises(TypeError):
            IncompleteExtractor()
