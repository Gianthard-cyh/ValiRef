"""Unit tests for exception handling in Pipeline, Detector, and Search."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio

from src.core.pipeline import ValidationPipeline
from src.core.detector import HallucinationDetector
from src.core.search.base import SearchTool
from src.core.exceptions import (
    ExtractionError,
    ValidationError,
    ValidationTimeoutError,
    AgentParseError,
    SearchError,
)
from src.bench.schema import Paper


class TestPipelineExceptions:
    """Tests for Pipeline exception handling."""

    @pytest.mark.asyncio
    async def test_extraction_failure_raises_extraction_error(self, tmp_path):
        """Extraction failure should raise ExtractionError, failing the task."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"fake pdf content")

        mock_extractor = MagicMock()
        mock_extractor.extract = AsyncMock(side_effect=Exception("PDF parse error"))

        pipeline = ValidationPipeline(
            extractor=mock_extractor,
            detector=MagicMock(),
        )

        with pytest.raises(ExtractionError) as exc_info:
            await pipeline.process_pdf(str(pdf_file))

        assert "PDF parse error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_single_validation_failure_returns_error_result(self, tmp_path):
        """Single reference validation failure should return error result, not raise."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"fake pdf content")

        papers = [
            Paper(
                source="reference",
                id="1",
                title="Paper 1",
                abstract="Abstract",
                authors=["Author"],
                published_date="2023",
                url="http://example.com/1",
            ),
            Paper(
                source="reference",
                id="2",
                title="Paper 2",
                abstract="Abstract",
                authors=["Author"],
                published_date="2023",
                url="http://example.com/2",
            ),
        ]

        mock_extractor = MagicMock()
        mock_extractor.extract = AsyncMock(return_value=papers)

        # First succeeds, second fails
        mock_validation_result = MagicMock()
        mock_validation_result.model_dump.return_value = {
            "hallucination_type": "Real",
            "confidence": 0.9,
            "reasoning": "Found",
            "evidence": [],
        }

        mock_detector = MagicMock()
        mock_detector.check_reference = AsyncMock(side_effect=[
            mock_validation_result,
            ValidationError("Validation failed"),
        ])

        pipeline = ValidationPipeline(
            extractor=mock_extractor,
            detector=mock_detector,
        )

        result = await pipeline.process_pdf(str(pdf_file), max_workers=1)

        # Task should complete successfully
        assert result["status"] == "completed"
        assert result["references_count"] == 2
        assert result["validated_count"] == 2
        # First success, second error
        assert result["results"][0]["status"] == "success"
        assert result["results"][1]["status"] == "error"

    @pytest.mark.asyncio
    async def test_all_validation_failures_returns_completed(self, tmp_path):
        """All references failing validation should still return completed status."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"fake pdf content")

        papers = [
            Paper(
                source="reference",
                id="1",
                title="Paper 1",
                abstract="Abstract",
                authors=["Author"],
                published_date="2023",
                url="http://example.com/1",
            ),
        ]

        mock_extractor = MagicMock()
        mock_extractor.extract = AsyncMock(return_value=papers)

        mock_detector = MagicMock()
        mock_detector.check_reference = AsyncMock(
            side_effect=ValidationError("All failed")
        )

        pipeline = ValidationPipeline(
            extractor=mock_extractor,
            detector=mock_detector,
        )

        result = await pipeline.process_pdf(str(pdf_file), max_workers=1)

        assert result["status"] == "completed"
        assert result["results"][0]["status"] == "error"

    @pytest.mark.asyncio
    async def test_unexpected_validation_error_raises(self, tmp_path):
        """Unexpected exceptions during validation should raise, not be captured."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"fake pdf content")

        papers = [
            Paper(
                source="reference",
                id="1",
                title="Paper 1",
                abstract="Abstract",
                authors=["Author"],
                published_date="2023",
                url="http://example.com/1",
            ),
        ]

        mock_extractor = MagicMock()
        mock_extractor.extract = AsyncMock(return_value=papers)

        # Unexpected error (not ValidationError subclass)
        mock_detector = MagicMock()
        mock_detector.check_reference = AsyncMock(
            side_effect=RuntimeError("Unexpected error")
        )

        pipeline = ValidationPipeline(
            extractor=mock_extractor,
            detector=mock_detector,
        )

        with pytest.raises(RuntimeError) as exc_info:
            await pipeline.process_pdf(str(pdf_file), max_workers=1)

        assert "Unexpected error" in str(exc_info.value)


class TestDetectorExceptions:
    """Tests for Detector exception handling."""

    @pytest.mark.asyncio
    async def test_timeout_raises_validation_timeout_error(self):
        """Agent timeout should raise ValidationTimeoutError."""
        detector = HallucinationDetector()

        mock_paper = Paper(
            source="reference",
            id="1",
            title="Test Paper",
            abstract="Abstract",
            authors=["Author"],
            published_date="2023",
            url="http://example.com",
        )

        with patch('asyncio.wait_for', side_effect=asyncio.TimeoutError()):
            with pytest.raises(ValidationTimeoutError) as exc_info:
                await detector.acheck_reference(mock_paper)

        assert "timeout" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_agent_parse_error_raises(self):
        """Agent output parsing failure should raise AgentParseError."""
        detector = HallucinationDetector()

        mock_paper = Paper(
            source="reference",
            id="1",
            title="Test Paper",
            abstract="Abstract",
            authors=["Author"],
            published_date="2023",
            url="http://example.com",
        )

        # Mock agent executor to return invalid format
        with patch.object(detector, 'agent_executor') as mock_executor:
            mock_executor.ainvoke = AsyncMock(return_value={
                "messages": [
                    MagicMock(tool_calls=[{
                        "name": "submit_validation_result",
                        "args": {"invalid": "format"}  # Missing required fields
                    }])
                ]
            })

            with pytest.raises(AgentParseError):
                await detector.acheck_reference(mock_paper)

    @pytest.mark.asyncio
    async def test_validation_error_raises(self):
        """General validation failure should raise ValidationError."""
        detector = HallucinationDetector()

        mock_paper = Paper(
            source="reference",
            id="1",
            title="Test Paper",
            abstract="Abstract",
            authors=["Author"],
            published_date="2023",
            url="http://example.com",
        )

        with patch.object(detector, 'agent_executor') as mock_executor:
            mock_executor.ainvoke = AsyncMock(side_effect=Exception("Agent failed"))

            with pytest.raises(ValidationError) as exc_info:
                await detector.acheck_reference(mock_paper)

        assert "Agent failed" in str(exc_info.value)


class TestSearchExceptions:
    """Tests for Search exception handling."""

    @pytest.mark.asyncio
    async def test_search_failure_raises_search_error(self):
        """Search failure should raise SearchError."""
        # Create a concrete implementation for testing
        class TestSearch(SearchTool):
            async def _perform_asearch(self, query: str, limit: int):
                raise Exception("Connection failed")

        search = TestSearch()

        with pytest.raises(SearchError) as exc_info:
            await search.asearch("test query")

        assert "Connection failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_http_error_raises_search_error(self):
        """HTTP error during search should raise SearchError."""
        import httpx

        class TestSearch(SearchTool):
            async def _perform_asearch(self, query: str, limit: int):
                raise httpx.HTTPError("500 Server Error")

        search = TestSearch()

        with pytest.raises(SearchError) as exc_info:
            await search.asearch("test query")

        assert "500 Server Error" in str(exc_info.value)
