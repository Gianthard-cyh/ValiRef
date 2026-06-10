"""
Unit tests for src.core.pipeline module with dependency injection.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from src.core.pipeline import ValidationPipeline
from src.bench.schema import Paper
from src.core.exceptions import ExtractionError, ValidationError


class TestValidationPipeline:
    """Tests for ValidationPipeline with dependency injection."""

    def test_constructor_with_mock_dependencies(self):
        """Test ValidationPipeline accepts mocked dependencies via constructor."""
        mock_extractor = MagicMock()
        mock_detector = MagicMock()
        mock_callback = MagicMock()

        pipeline = ValidationPipeline(
            extractor=mock_extractor,
            detector=mock_detector,
            callbacks=[mock_callback],
        )

        assert pipeline.extractor == mock_extractor
        assert pipeline.detector == mock_detector
        assert pipeline.callbacks == [mock_callback]

    def test_constructor_creates_default_dependencies(self):
        """Test pipeline creates default dependencies when not provided."""
        with (
            patch("src.core.pipeline.PDFExtractor") as mock_extractor_cls,
            patch("src.core.pipeline.HallucinationDetector") as mock_detector_cls,
        ):
            mock_extractor = MagicMock()
            mock_detector = MagicMock()
            mock_extractor_cls.return_value = mock_extractor
            mock_detector_cls.return_value = mock_detector

            pipeline = ValidationPipeline()

            assert pipeline.extractor == mock_extractor
            assert pipeline.detector == mock_detector
            assert pipeline.callbacks == []

    @pytest.mark.asyncio
    async def test_process_with_mock_dependencies(self, tmp_path):
        """Test process with fully mocked dependencies."""
        # Create a temporary PDF file
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"fake pdf content")

        # Setup mocks
        mock_paper = Paper(
            source="reference",
            id="123",
            title="Test Paper",
            abstract="Abstract",
            authors=["Author"],
            published_date="2023",
            url="http://example.com",
        )

        mock_extractor = MagicMock()
        mock_extractor.extract = AsyncMock(return_value=[mock_paper])

        mock_validation_result = MagicMock()
        mock_validation_result.model_dump.return_value = {
            "hallucination_type": "Real",
            "confidence": 0.95,
            "reasoning": "Found in OpenAlex",
            "evidence": ["http://example.com"],
        }

        mock_detector = MagicMock()
        mock_detector.check_reference = AsyncMock(return_value=mock_validation_result)

        mock_callback = AsyncMock()

        pipeline = ValidationPipeline(
            extractor=mock_extractor,
            detector=mock_detector,
            callbacks=[mock_callback],
        )

        # Execute
        result = await pipeline.process(str(pdf_file), max_workers=1)

        # Verify
        assert result["file"] == "test.pdf"
        assert result["references_count"] == 1
        assert result["validated_count"] == 1
        assert result["status"] == "completed"

        mock_extractor.extract.assert_called_once()
        mock_detector.check_reference.assert_called_once_with(mock_paper)

    @pytest.mark.asyncio
    async def test_process_notifies_callbacks(self, tmp_path):
        """Test process notifies callbacks at each stage."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"fake pdf content")

        mock_paper = Paper(
            source="reference",
            id="123",
            title="Test Paper",
            abstract="Abstract",
            authors=["Author"],
            published_date="2023",
            url="http://example.com",
        )

        mock_extractor = MagicMock()
        mock_extractor.extract = AsyncMock(return_value=[mock_paper])

        mock_validation_result = MagicMock()
        mock_validation_result.model_dump.return_value = {
            "hallucination_type": "Real",
            "confidence": 0.95,
            "reasoning": "Found",
            "evidence": [],
        }

        mock_detector = MagicMock()
        mock_detector.check_reference = AsyncMock(return_value=mock_validation_result)

        mock_callback = AsyncMock()

        pipeline = ValidationPipeline(
            extractor=mock_extractor,
            detector=mock_detector,
            callbacks=[mock_callback],
        )

        await pipeline.process(str(pdf_file), max_workers=1)

        # Verify callbacks were called
        mock_callback.on_pipeline_start.assert_called_once_with("test.pdf")
        mock_callback.on_extraction_start.assert_called_once_with("test.pdf")
        mock_callback.on_extraction_end.assert_called_once()
        mock_callback.on_validation_start.assert_called_once_with(1)
        mock_callback.on_reference_validation_start.assert_called_once()
        mock_callback.on_reference_validation_end.assert_called_once()
        mock_callback.on_pipeline_end.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_raises_on_extraction_error(self, tmp_path):
        """Test process raises ExtractionError on extraction failure."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"fake pdf content")

        mock_extractor = MagicMock()
        mock_extractor.extract = AsyncMock(side_effect=Exception("Extraction failed"))

        mock_callback = AsyncMock()

        pipeline = ValidationPipeline(
            extractor=mock_extractor,
            detector=MagicMock(),
            callbacks=[mock_callback],
        )

        with pytest.raises(ExtractionError):
            await pipeline.process(str(pdf_file), max_workers=1)

        mock_callback.on_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_handles_empty_references(self, tmp_path):
        """Test process when no references are found."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"fake pdf content")

        mock_extractor = MagicMock()
        mock_extractor.extract = AsyncMock(return_value=[])

        pipeline = ValidationPipeline(
            extractor=mock_extractor,
            detector=MagicMock(),
        )

        result = await pipeline.process(str(pdf_file), max_workers=1)

        assert result["references_count"] == 0
        assert result["validated_count"] == 0
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_process_handles_validation_errors(self, tmp_path):
        """Test process handles validation errors for individual references."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"fake pdf content")

        mock_paper = Paper(
            source="reference",
            id="123",
            title="Test Paper",
            abstract="Abstract",
            authors=["Author"],
            published_date="2023",
            url="http://example.com",
        )

        mock_extractor = MagicMock()
        mock_extractor.extract = AsyncMock(return_value=[mock_paper])

        mock_detector = MagicMock()
        mock_detector.check_reference = AsyncMock(
            side_effect=ValidationError("Validation failed")
        )

        mock_callback = AsyncMock()

        pipeline = ValidationPipeline(
            extractor=mock_extractor,
            detector=mock_detector,
            callbacks=[mock_callback],
        )

        result = await pipeline.process(str(pdf_file), max_workers=1)

        # Should still complete, but with error result for that reference
        assert result["status"] == "completed"
        assert result["references_count"] == 1
        assert result["validated_count"] == 1  # Error is captured as a result
        assert result["results"][0]["status"] == "error"

    def test_process_raises_for_missing_file(self):
        """Test process raises error for non-existent file."""
        mock_callback = AsyncMock()

        pipeline = ValidationPipeline(
            extractor=MagicMock(),
            detector=MagicMock(),
            callbacks=[mock_callback],
        )

        with pytest.raises(FileNotFoundError):
            # asyncio.run to handle the async nature
            import asyncio

            asyncio.run(pipeline.process("/nonexistent/file.pdf"))

    @pytest.mark.asyncio
    async def test_process_concurrent_validation(self, tmp_path):
        """Test process validates multiple references concurrently."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"fake pdf content")

        papers = [
            Paper(
                source="reference",
                id=f"{i}",
                title=f"Paper {i}",
                abstract="Abstract",
                authors=["Author"],
                published_date="2023",
                url=f"http://example.com/{i}",
            )
            for i in range(3)
        ]

        mock_extractor = MagicMock()
        mock_extractor.extract = AsyncMock(return_value=papers)

        mock_validation_result = MagicMock()
        mock_validation_result.model_dump.return_value = {
            "hallucination_type": "Real",
            "confidence": 0.9,
            "reasoning": "Found",
            "evidence": [],
        }

        mock_detector = MagicMock()
        mock_detector.check_reference = AsyncMock(return_value=mock_validation_result)

        pipeline = ValidationPipeline(
            extractor=mock_extractor,
            detector=mock_detector,
        )

        result = await pipeline.process(str(pdf_file), max_workers=2)

        assert result["references_count"] == 3
        assert result["validated_count"] == 3
        assert mock_detector.check_reference.call_count == 3

    @pytest.mark.asyncio
    async def test_process_bibtex_file(self, tmp_path):
        """Test process with BibTeXExtractor mock."""
        bib_file = tmp_path / "test.bib"
        bib_file.write_text("dummy")

        mock_paper = Paper(
            source="bibtex",
            id="N/A",
            title="BibTeX Paper",
            abstract="Abstract",
            authors=["Author"],
            published_date="2023",
            url="N/A",
        )

        mock_extractor = MagicMock()
        mock_extractor.extract = AsyncMock(return_value=[mock_paper])

        mock_validation_result = MagicMock()
        mock_validation_result.model_dump.return_value = {
            "hallucination_type": "Real",
            "confidence": 0.9,
            "reasoning": "Found",
            "evidence": [],
        }

        mock_detector = MagicMock()
        mock_detector.check_reference = AsyncMock(return_value=mock_validation_result)

        pipeline = ValidationPipeline(
            extractor=mock_extractor,
            detector=mock_detector,
        )

        result = await pipeline.process(str(bib_file), max_workers=1)

        assert result["file"] == "test.bib"
        assert result["references_count"] == 1
        assert result["validated_count"] == 1
        mock_extractor.extract.assert_called_once()
