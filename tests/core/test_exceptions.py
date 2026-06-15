"""Unit tests for exception handling in Pipeline, Detector, and Search."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio

from src.core.pipeline import ValidationPipeline
from src.core.detector import HallucinationDetector
from src.core.search.base import SearchTool
from src.core.exceptions import (
    ValirefError,
    ExtractionError,
    ValidationError,
    ValidationTimeoutError,
    AgentParseError,
    SearchError,
    ErrorCode,
)
from src.bench.schema import Paper


class TestValirefErrorBase:
    """Tests for base ValirefError with error_code."""

    def test_error_without_error_code(self):
        """ValirefError can be created without error_code (backward compatible)."""
        err = ValirefError("Something went wrong")
        assert str(err) == "Something went wrong"
        assert err.message == "Something went wrong"
        assert err.error_code is None

    def test_error_with_error_code(self):
        """ValirefError can have error_code for frontend."""
        err = ValirefError("PDF corrupted", error_code=ErrorCode.PDF_CORRUPTED)
        assert str(err) == "PDF corrupted"
        assert err.message == "PDF corrupted"
        assert err.error_code == "pdf_corrupted"

    def test_error_code_constants(self):
        """ErrorCode constants should be strings."""
        assert ErrorCode.PDF_CORRUPTED == "pdf_corrupted"
        assert ErrorCode.PDF_NO_TEXT == "pdf_no_text"
        assert ErrorCode.PDF_TOO_SHORT == "pdf_too_short"
        assert ErrorCode.EXTRACTION_FAILED == "extraction_failed"
        assert ErrorCode.NO_REFERENCES_FOUND == "no_references_found"
        assert ErrorCode.VALIDATION_TIMEOUT == "validation_timeout"
        assert ErrorCode.SEARCH_FAILED == "search_failed"
        assert ErrorCode.AGENT_PARSE_ERROR == "agent_parse_error"


class TestExtractionErrorWithErrorCode:
    """Tests for ExtractionError with error_code."""

    def test_extraction_error_inherits_error_code(self):
        """ExtractionError inherits error_code from ValirefError."""
        err = ExtractionError("PDF corrupted", error_code=ErrorCode.PDF_CORRUPTED)
        assert err.error_code == "pdf_corrupted"
        assert isinstance(err, ValirefError)

    def test_extraction_error_without_code(self):
        """ExtractionError works without error_code."""
        err = ExtractionError("Generic extraction failure")
        assert err.error_code is None


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
            await pipeline.process(str(pdf_file))

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

        result = await pipeline.process(str(pdf_file), max_workers=1)

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

        result = await pipeline.process(str(pdf_file), max_workers=1)

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
            await pipeline.process(str(pdf_file), max_workers=1)

        assert "Unexpected error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_agent_timeout_returns_completed(self, tmp_path):
        """Agent timeout should return error result, not fail the entire pipeline."""
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

        # First succeeds, second times out
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
            ValidationTimeoutError("Agent timeout after 120s"),
        ])

        pipeline = ValidationPipeline(
            extractor=mock_extractor,
            detector=mock_detector,
        )

        result = await pipeline.process(str(pdf_file), max_workers=1)

        # Pipeline should complete successfully despite timeout
        assert result["status"] == "completed"
        assert result["references_count"] == 2
        assert result["validated_count"] == 2
        # First success, second timeout
        assert result["results"][0]["status"] == "success"
        assert result["results"][1]["status"] == "error"
        assert "timeout" in result["results"][1]["validation"]["reasoning"].lower()


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
