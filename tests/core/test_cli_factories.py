"""
Unit tests for CLI factory functions with dependency injection.
"""

import pytest
from unittest.mock import MagicMock, patch

from src.cli import create_llm, create_detector, create_pipeline
from src.core.detector import HallucinationDetector


class TestCreateLLM:
    """Tests for create_llm factory function."""

    def test_create_llm_with_default_temperature(self):
        """Test create_llm with default temperature."""
        with patch("src.cli.ChatDeepSeek") as mock_llm_cls:
            mock_llm = MagicMock()
            mock_llm_cls.return_value = mock_llm

            with patch("src.cli.DEEPSEEK_API_KEY", "test-api-key"):
                llm = create_llm()

            assert llm == mock_llm
            mock_llm_cls.assert_called_once()
            call_kwargs = mock_llm_cls.call_args.kwargs
            assert call_kwargs["temperature"] == 0.7  # Default LLM_TEMPERATURE

    def test_create_llm_with_custom_temperature(self):
        """Test create_llm with custom temperature."""
        with patch("src.cli.ChatDeepSeek") as mock_llm_cls:
            mock_llm = MagicMock()
            mock_llm_cls.return_value = mock_llm

            with patch("src.cli.DEEPSEEK_API_KEY", "test-api-key"):
                llm = create_llm(temperature=0.1)

            call_kwargs = mock_llm_cls.call_args.kwargs
            assert call_kwargs["temperature"] == 0.1

    def test_create_llm_raises_without_api_key(self):
        """Test create_llm raises error when API key is not set."""
        with patch("src.cli.DEEPSEEK_API_KEY", None):
            with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
                create_llm()


class TestCreateDetector:
    """Tests for create_detector factory function."""

    def test_create_detector_with_provided_llm(self):
        """Test create_detector with provided LLM."""
        mock_llm = MagicMock()

        with patch("src.cli.AggregateSearchFactory") as mock_factory:
            mock_search = MagicMock()
            mock_factory.create.return_value = mock_search

            with patch.object(HallucinationDetector, "_get_tools", return_value=[]):
                with patch("src.core.detector.create_agent"):
                    detector = create_detector(llm=mock_llm)

                    assert detector.llm == mock_llm
                    assert detector.aggregate_search_instance == mock_search

    def test_create_detector_creates_new_llm_when_not_provided(self):
        """Test create_detector creates new LLM when not provided."""
        with patch("src.cli.create_llm") as mock_create_llm:
            mock_llm = MagicMock()
            mock_create_llm.return_value = mock_llm

            with patch("src.cli.AggregateSearchFactory"):
                with patch.object(HallucinationDetector, "_get_tools", return_value=[]):
                    with patch("src.core.detector.create_agent"):
                        create_detector()

            mock_create_llm.assert_called_once_with(
                temperature=0.1
            )  # DETECTOR_TEMPERATURE


class TestCreatePipeline:
    """Tests for create_pipeline factory function."""

    def test_create_pipeline_assembles_dependencies(self):
        """Test create_pipeline correctly assembles all dependencies."""
        with (
            patch("src.cli.create_llm") as mock_create_llm,
            patch("src.cli.create_detector") as mock_create_detector,
        ):
            mock_llm = MagicMock()
            mock_create_llm.return_value = mock_llm

            mock_detector = MagicMock()
            mock_create_detector.return_value = mock_detector

            with (
                patch("src.cli.TextExtractor") as mock_text_extractor_cls,
                patch("src.cli.PDFExtractor") as mock_pdf_extractor_cls,
                patch("src.cli.ValidationPipeline") as mock_pipeline_cls,
            ):
                mock_text_extractor = MagicMock()
                mock_pdf_extractor = MagicMock()
                mock_pipeline = MagicMock()

                mock_text_extractor_cls.return_value = mock_text_extractor
                mock_pdf_extractor_cls.return_value = mock_pdf_extractor
                mock_pipeline_cls.return_value = mock_pipeline

                result = create_pipeline()

                # Verify dependencies were created
                mock_create_llm.assert_called_once()
                mock_text_extractor_cls.assert_called_once_with(llm=mock_llm)
                mock_pdf_extractor_cls.assert_called_once_with(
                    text_extractor=mock_text_extractor
                )
                mock_create_detector.assert_called_once()

                # Verify pipeline was created with correct dependencies
                mock_pipeline_cls.assert_called_once()
                call_kwargs = mock_pipeline_cls.call_args.kwargs
                assert call_kwargs["extractor"] == mock_pdf_extractor
                assert call_kwargs["detector"] == mock_detector
                assert call_kwargs["callbacks"] == []

    def test_create_pipeline_with_callbacks(self):
        """Test create_pipeline accepts callbacks."""
        mock_callback = MagicMock()

        with (
            patch("src.cli.create_llm") as mock_create_llm,
            patch("src.cli.create_detector") as mock_create_detector,
            patch("src.cli.TextExtractor"),
            patch("src.cli.PDFExtractor"),
            patch("src.cli.ValidationPipeline") as mock_pipeline_cls,
        ):
            mock_llm = MagicMock()
            mock_create_llm.return_value = mock_llm

            mock_detector = MagicMock()
            mock_create_detector.return_value = mock_detector

            create_pipeline(callbacks=[mock_callback])

            call_kwargs = mock_pipeline_cls.call_args.kwargs
            assert call_kwargs["callbacks"] == [mock_callback]


class TestDependencyInjectionE2E:
    """End-to-end tests demonstrating the dependency injection benefits."""

    def test_can_swap_llm_implementation(self):
        """Test that we can swap the LLM implementation."""
        # This demonstrates the power of DI - we can inject a custom LLM
        custom_llm = MagicMock()

        with patch("src.cli.AggregateSearchFactory"):
            with patch.object(HallucinationDetector, "_get_tools", return_value=[]):
                with patch("src.core.detector.create_agent"):
                    detector = HallucinationDetector(llm=custom_llm)

                    assert detector.llm is custom_llm

    def test_can_create_isolated_test_detector(self):
        """Test that we can create isolated detector for testing."""
        # Create a detector with completely mocked dependencies
        mock_llm = MagicMock()
        mock_search = MagicMock()

        with patch.object(HallucinationDetector, "_get_tools", return_value=[]):
            with patch("src.core.detector.create_agent"):
                detector = HallucinationDetector(
                    llm=mock_llm,
                    search=mock_search,
                )

                assert detector.llm is mock_llm
                assert detector.aggregate_search_instance is mock_search
        assert detector.aggregate_search_instance is mock_search
