"""
Unit tests for benchmark reporter module.
"""

from unittest.mock import MagicMock, patch

from src.bench.reporter import BenchmarkReporter, print_results
from src.bench.metrics.dataclasses import BenchmarkResult, MultiClassMetrics, SampleResult
from src.bench.schema import Paper
from src.core.detector import ValidationResult


class TestBenchmarkReporter:
    """Tests for BenchmarkReporter class."""

    def test_reporter_has_print_results_method(self):
        """Test that BenchmarkReporter has print_results method."""
        reporter = BenchmarkReporter()
        assert hasattr(reporter, 'print_results')
        assert callable(getattr(reporter, 'print_results'))

    def test_print_results_with_valid_result(self):
        """Test print_results can be called with a valid BenchmarkResult."""
        # Create a minimal BenchmarkResult
        metrics = MultiClassMetrics(
            accuracy=0.8,
            total_samples=2,
            confusion_matrix={
                "Real": {"Real": 1, "Fabrication": 0},
                "Fabrication": {"Real": 0, "Fabrication": 1},
            },
            per_class_precision={"Real": 1.0, "Fabrication": 1.0},
            per_class_recall={"Real": 1.0, "Fabrication": 1.0},
            per_class_f1={"Real": 1.0, "Fabrication": 1.0},
            per_class_support={"Real": 1, "Fabrication": 1},
            macro_precision=1.0,
            macro_recall=1.0,
            macro_f1=1.0,
            micro_precision=1.0,
            micro_recall=1.0,
            micro_f1=1.0,
            weighted_precision=1.0,
            weighted_recall=1.0,
            weighted_f1=1.0,
        )

        paper = Paper(
            source="test",
            id="test-1",
            title="Test Paper",
            abstract="Test abstract",
            authors=["Author 1"],
            published_date="2024-01-01",
            url="http://example.com",
        )

        prediction = ValidationResult(
            hallucination_type="Real",
            confidence=0.9,
            reasoning="Test reasoning",
            evidence=[],
        )

        sample = SampleResult(
            paper=paper,
            prediction=prediction,
            ground_truth_type="Real",
            correct=True,
        )

        result = BenchmarkResult(
            metrics=metrics,
            per_type_metrics={"Real": metrics},
            samples=[sample],
            duration_seconds=1.0,
        )

        # Should not raise any exception
        reporter = BenchmarkReporter()
        reporter.print_results(result)

    def test_standalone_print_results_function(self):
        """Test the standalone print_results function works correctly."""
        # Create a minimal BenchmarkResult
        metrics = MultiClassMetrics(
            accuracy=1.0,
            total_samples=1,
            confusion_matrix={"Real": {"Real": 1}},
            per_class_precision={"Real": 1.0},
            per_class_recall={"Real": 1.0},
            per_class_f1={"Real": 1.0},
            per_class_support={"Real": 1},
            macro_precision=1.0,
            macro_recall=1.0,
            macro_f1=1.0,
            micro_precision=1.0,
            micro_recall=1.0,
            micro_f1=1.0,
            weighted_precision=1.0,
            weighted_recall=1.0,
            weighted_f1=1.0,
        )

        paper = Paper(
            source="test",
            id="test-1",
            title="Test Paper",
            abstract="Test abstract",
            authors=["Author 1"],
            published_date="2024-01-01",
            url="http://example.com",
        )

        prediction = ValidationResult(
            hallucination_type="Real",
            confidence=0.9,
            reasoning="Test reasoning",
            evidence=[],
        )

        sample = SampleResult(
            paper=paper,
            prediction=prediction,
            ground_truth_type="Real",
            correct=True,
        )

        result = BenchmarkResult(
            metrics=metrics,
            per_type_metrics={},
            samples=[sample],
            duration_seconds=1.0,
        )

        # Should not raise any exception
        print_results(result)

    def test_benchmark_runner_does_not_have_print_results(self):
        """Test that BenchmarkRunner does not have print_results method (regression test)."""
        from src.bench.runner import BenchmarkRunner

        # BenchmarkRunner should NOT have print_results as a method
        assert not hasattr(BenchmarkRunner, 'print_results') or not callable(getattr(BenchmarkRunner, 'print_results', None)), \
            "BenchmarkRunner should not have print_results method - it should use the standalone function"


class TestCLIBenchmarkIntegration:
        """Tests for CLI benchmark command integration."""

        @patch("src.cli.print_results")
        @patch("src.cli.BenchmarkRunner")
        @patch("src.cli.create_detector")
        @patch("src.cli.asyncio.run")
        @patch("src.cli.console")
        @patch("pathlib.Path.exists")
        def test_cli_calls_print_results_function_not_method(
            self, mock_exists, mock_console, mock_run, mock_create_detector, mock_runner_cls, mock_print_results
        ):
            """Test that CLI calls print_results as a function, not as a method on runner.

            This is a regression test for the bug where `runner.print_results(result)`
            was called but BenchmarkRunner doesn't have this method.
            """
            from src.cli import benchmark

            # Setup mocks
            mock_exists.return_value = True
            mock_detector = MagicMock()
            mock_create_detector.return_value = mock_detector

            mock_runner = MagicMock()
            mock_runner_cls.return_value = mock_runner

            # Create a mock result
            mock_metrics = MagicMock()
            mock_metrics.accuracy = 0.8
            mock_metrics.total_samples = 2

            mock_result = MagicMock()
            mock_result.metrics = mock_metrics
            mock_result.samples = []
            mock_result.duration_seconds = 1.0
            mock_result.to_dict.return_value = {"accuracy": 0.8}

            mock_run.return_value = mock_result

            # Call the benchmark command
            benchmark(
                dataset_path="test.csv",
                output=None,
                workers=1,
                limit=1,
                verbose=False,
                show_metrics=False,
                search_mode="hybrid",
            )

            # Verify print_results was called as a function, not as runner.print_results
            mock_print_results.assert_called_once_with(mock_result)
            mock_runner.print_results.assert_not_called()  # This should NOT be called
