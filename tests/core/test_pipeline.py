"""
Unit tests for src.core.pipeline module with dependency injection.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path

from src.core.pipeline import ValidationPipeline
from src.bench.schema import Paper


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
        with patch("src.core.pipeline.PDFExtractor") as mock_extractor_cls, \
             patch("src.core.pipeline.HallucinationDetector") as mock_detector_cls:

            mock_extractor = MagicMock()
            mock_detector = MagicMock()
            mock_extractor_cls.return_value = mock_extractor
            mock_detector_cls.return_value = mock_detector

            pipeline = ValidationPipeline()

            assert pipeline.extractor == mock_extractor
            assert pipeline.detector == mock_detector
            assert pipeline.callbacks == []

    @pytest.mark.asyncio
    async def test_process_pdf_with_mock_dependencies(self, tmp_path):
        """Test process_pdf with fully mocked dependencies."""
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
            "is_hallucination": False,
            "confidence": 0.95,
            "reasoning": "Found in OpenAlex",
            "evidence": ["http://example.com"],
        }

        mock_detector = MagicMock()
        mock_detector.check_reference = AsyncMock(return_value=mock_validation_result)

        mock_callback = MagicMock()

        pipeline = ValidationPipeline(
            extractor=mock_extractor,
            detector=mock_detector,
            callbacks=[mock_callback],
        )

        # Execute
        result = await pipeline.process_pdf(str(pdf_file), max_workers=1)

        # Verify
        assert result["file"] == "test.pdf"
        assert result["references_count"] == 1
        assert result["validated_count"] == 1
        assert result["status"] == "completed"

        mock_extractor.extract.assert_called_once()
        mock_detector.check_reference.assert_called_once_with(mock_paper)

    @pytest.mark.asyncio
    async def test_process_pdf_notifies_callbacks(self, tmp_path):
        """Test process_pdf notifies callbacks at each stage."""
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
            "is_hallucination": False,
            "confidence": 0.95,
            "reasoning": "Found",
            "evidence": [],
        }

        mock_detector = MagicMock()
        mock_detector.check_reference = AsyncMock(return_value=mock_validation_result)

        mock_callback = MagicMock()

        pipeline = ValidationPipeline(
            extractor=mock_extractor,
            detector=mock_detector,
            callbacks=[mock_callback],
        )

        await pipeline.process_pdf(str(pdf_file), max_workers=1)

        # Verify callbacks were called
        mock_callback.on_pipeline_start.assert_called_once_with("test.pdf")
        mock_callback.on_extraction_start.assert_called_once_with("test.pdf")
        mock_callback.on_extraction_end.assert_called_once()
        mock_callback.on_validation_start.assert_called_once_with(1)
        mock_callback.on_reference_validation_start.assert_called_once()
        mock_callback.on_reference_validation_end.assert_called_once()
        mock_callback.on_pipeline_end.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_pdf_handles_extraction_error(self, tmp_path):
        """Test process_pdf handles extraction errors gracefully."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"fake pdf content")

        mock_extractor = MagicMock()
        mock_extractor.extract = AsyncMock(side_effect=Exception("Extraction failed"))

        mock_callback = MagicMock()

        pipeline = ValidationPipeline(
            extractor=mock_extractor,
            detector=MagicMock(),
            callbacks=[mock_callback],
        )

        result = await pipeline.process_pdf(str(pdf_file), max_workers=1)

        assert result["status"] == "failed"
        assert "error" in result
        mock_callback.on_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_pdf_handles_empty_references(self, tmp_path):
        """Test process_pdf when no references are found."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"fake pdf content")

        mock_extractor = MagicMock()
        mock_extractor.extract = AsyncMock(return_value=[])

        pipeline = ValidationPipeline(
            extractor=mock_extractor,
            detector=MagicMock(),
        )

        result = await pipeline.process_pdf(str(pdf_file), max_workers=1)

        assert result["references_count"] == 0
        assert result["validated_count"] == 0
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_process_pdf_handles_validation_errors(self, tmp_path):
        """Test process_pdf handles validation errors for individual references."""
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
        mock_detector.check_reference = AsyncMock(side_effect=Exception("Validation failed"))

        mock_callback = MagicMock()

        pipeline = ValidationPipeline(
            extractor=mock_extractor,
            detector=mock_detector,
            callbacks=[mock_callback],
        )

        result = await pipeline.process_pdf(str(pdf_file), max_workers=1)

        # Should still complete, but with error result for that reference
        assert result["status"] == "completed"
        assert result["references_count"] == 1
        assert result["validated_count"] == 1  # Error is captured as a result

    def test_process_pdf_raises_for_missing_file(self):
        """Test process_pdf raises error for non-existent file."""
        mock_callback = MagicMock()

        pipeline = ValidationPipeline(
            extractor=MagicMock(),
            detector=MagicMock(),
            callbacks=[mock_callback],
        )

        with pytest.raises(FileNotFoundError):
            # asyncio.run to handle the async nature
            import asyncio
            asyncio.run(pipeline.process_pdf("/nonexistent/file.pdf"))

    @pytest.mark.asyncio
    async def test_process_pdf_concurrent_validation(self, tmp_path):
        """Test process_pdf validates multiple references concurrently."""
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
            "is_hallucination": False,
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

        result = await pipeline.process_pdf(str(pdf_file), max_workers=2)

        assert result["references_count"] == 3
        assert result["validated_count"] == 3
        assert mock_detector.check_reference.call_count == 3
