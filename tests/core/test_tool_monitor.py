"""Tests for tool monitor."""

import time
from datetime import datetime, timedelta

import pytest

from src.core.tool_monitor import (
    ToolStats,
    ToolMetricsCollector,
    format_circuit_state,
    CIRCUIT_STATE_DISPLAY,
)


class TestToolStats:
    """Tests for ToolStats."""

    def test_initial_state(self):
        stats = ToolStats(tool_name="test_tool")

        assert stats.tool_name == "test_tool"
        assert stats.total_calls == 0
        assert stats.successful_calls == 0
        assert stats.failed_calls == 0
        assert stats.avg_duration_ms == 0
        assert stats.active_tasks == 0
        assert stats.min_duration_ms == float("inf")

    def test_avg_duration_calculation(self):
        stats = ToolStats(tool_name="test")
        stats.total_calls = 2
        stats.total_duration_ms = 100.0

        assert stats.avg_duration_ms == 50.0

    def test_avg_results_calculation(self):
        stats = ToolStats(tool_name="test")
        stats.total_calls = 2
        stats.total_results = 10

        assert stats.avg_results == 5.0

    def test_calls_per_minute(self):
        stats = ToolStats(tool_name="test")

        # Record some calls
        stats.record_call()
        stats.record_call()
        stats.record_call()

        assert stats.calls_per_minute == 3

    def test_calls_per_minute_filters_old_calls(self):
        stats = ToolStats(tool_name="test")

        # Add an old call manually
        old_time = datetime.now() - timedelta(seconds=120)
        stats._call_history.append(old_time)

        # Add recent calls
        stats.record_call()
        stats.record_call()

        assert stats.calls_per_minute == 2

    def test_to_dict(self):
        stats = ToolStats(tool_name="test")
        stats.total_calls = 10
        stats.successful_calls = 8
        stats.failed_calls = 2
        stats.total_duration_ms = 500.0
        stats.max_duration_ms = 100.0
        stats.min_duration_ms = 10.0
        stats.total_results = 50
        stats.active_tasks = 1

        result = stats.to_dict()

        assert result["tool_name"] == "test"
        assert result["total_calls"] == 10
        assert result["successful_calls"] == 8
        assert result["failed_calls"] == 2
        assert result["avg_duration_ms"] == 50.0
        assert result["max_duration_ms"] == 100.0
        assert result["min_duration_ms"] == 10.0
        assert result["avg_results"] == 5.0
        assert result["active_tasks"] == 1

    def test_to_dict_with_inf_min_duration(self):
        stats = ToolStats(tool_name="test")
        stats.total_calls = 0
        stats.min_duration_ms = float("inf")

        result = stats.to_dict()

        assert result["min_duration_ms"] == 0


class TestFormatCircuitState:
    """Tests for format_circuit_state."""

    def test_closed_state(self):
        text, color = format_circuit_state("CLOSED")
        assert "Normal" in text
        assert color == "green"

    def test_half_open_state(self):
        text, color = format_circuit_state("HALF_OPEN")
        assert "Recovering" in text
        assert color == "yellow"

    def test_open_state(self):
        text, color = format_circuit_state("OPEN")
        assert "Open" in text
        assert color == "red"

    def test_unknown_state(self):
        text, color = format_circuit_state("UNKNOWN")
        assert "UNKNOWN" in text
        assert color == "white"


class TestToolMetricsCollector:
    """Tests for ToolMetricsCollector."""

    def test_initial_state(self):
        collector = ToolMetricsCollector()

        summary = collector.get_summary()
        assert summary["total_calls"] == 0
        assert summary["by_tool"] == {}

    def test_signal_handling_started(self):
        updates = []
        collector = ToolMetricsCollector(on_update=lambda: updates.append(1))

        from src.core.tool_monitor import tool_call_started

        tool_call_started.send(
            "test",
            tool_name="ArxivSearch",
            query="test query",
            start_time=datetime.now(),
        )

        summary = collector.get_summary()
        assert summary["by_tool"]["ArxivSearch"]["active_tasks"] == 1
        assert len(updates) == 1

    def test_signal_handling_completed(self):
        collector = ToolMetricsCollector()

        from src.core.tool_monitor import tool_call_started, tool_call_ended

        start_time = datetime.now()

        tool_call_started.send(
            "test",
            tool_name="ArxivSearch",
            query="test query",
            start_time=start_time,
        )

        tool_call_ended.send(
            "test",
            tool_name="ArxivSearch",
            query="test query",
            end_time=datetime.now(),
            duration_ms=100.0,
            success=True,
            result_count=5,
            error_type=None,
        )

        summary = collector.get_summary()
        tool_stats = summary["by_tool"]["ArxivSearch"]

        assert tool_stats["total_calls"] == 1
        assert tool_stats["successful_calls"] == 1
        assert tool_stats["failed_calls"] == 0
        assert tool_stats["avg_duration_ms"] == 100.0
        assert tool_stats["active_tasks"] == 0

    def test_signal_handling_failed(self):
        collector = ToolMetricsCollector()

        from src.core.tool_monitor import tool_call_started, tool_call_ended

        tool_call_started.send(
            "test",
            tool_name="ArxivSearch",
            query="test query",
            start_time=datetime.now(),
        )

        tool_call_ended.send(
            "test",
            tool_name="ArxivSearch",
            query="test query",
            end_time=datetime.now(),
            duration_ms=50.0,
            success=False,
            result_count=0,
            error_type="TimeoutError",
        )

        summary = collector.get_summary()
        tool_stats = summary["by_tool"]["ArxivSearch"]

        assert tool_stats["total_calls"] == 1
        assert tool_stats["successful_calls"] == 0
        assert tool_stats["failed_calls"] == 1
        assert tool_stats["errors"]["TimeoutError"] == 1

    def test_multiple_tools_tracked_separately(self):
        collector = ToolMetricsCollector()

        from src.core.tool_monitor import tool_call_started, tool_call_ended

        # Tool 1
        tool_call_started.send("test", tool_name="ArxivSearch", query="q1", start_time=datetime.now())
        tool_call_ended.send("test", tool_name="ArxivSearch", query="q1", end_time=datetime.now(), duration_ms=10.0, success=True, result_count=3, error_type=None)

        # Tool 2
        tool_call_started.send("test", tool_name="ScholarlySearch", query="q2", start_time=datetime.now())
        tool_call_ended.send("test", tool_name="ScholarlySearch", query="q2", end_time=datetime.now(), duration_ms=20.0, success=True, result_count=5, error_type=None)

        summary = collector.get_summary()

        assert summary["total_calls"] == 2
        assert summary["by_tool"]["ArxivSearch"]["total_calls"] == 1
        assert summary["by_tool"]["ScholarlySearch"]["total_calls"] == 1

    def test_reset_clears_stats(self):
        collector = ToolMetricsCollector()

        from src.core.tool_monitor import tool_call_started, tool_call_ended

        tool_call_started.send("test", tool_name="ArxivSearch", query="q", start_time=datetime.now())
        tool_call_ended.send("test", tool_name="ArxivSearch", query="q", end_time=datetime.now(), duration_ms=10.0, success=True, result_count=3, error_type=None)

        collector.reset()

        summary = collector.get_summary()
        assert summary["total_calls"] == 0
        assert summary["by_tool"] == {}

    def test_derive_circuit_state_closed(self):
        collector = ToolMetricsCollector()

        from src.core.tool_monitor import tool_call_started, tool_call_ended

        # Add successful calls
        for i in range(5):
            tool_call_started.send("test", tool_name="TestTool", query=f"q{i}", start_time=datetime.now())
            tool_call_ended.send("test", tool_name="TestTool", query=f"q{i}", end_time=datetime.now(), duration_ms=10.0, success=True, result_count=1, error_type=None)

        text, color = collector._derive_circuit_state(collector._stats["TestTool"].to_dict())
        assert "Normal" in text

    def test_derive_circuit_state_open(self):
        collector = ToolMetricsCollector()

        from src.core.tool_monitor import tool_call_started, tool_call_ended

        # Add failed calls
        for i in range(5):
            tool_call_started.send("test", tool_name="TestTool", query=f"q{i}", start_time=datetime.now())
            tool_call_ended.send("test", tool_name="TestTool", query=f"q{i}", end_time=datetime.now(), duration_ms=10.0, success=False, result_count=0, error_type="Error")

        text, color = collector._derive_circuit_state(collector._stats["TestTool"].to_dict())
        assert "Open" in text
        assert color == "red"

    def test_derive_circuit_state_half_open(self):
        collector = ToolMetricsCollector()

        from src.core.tool_monitor import tool_call_started, tool_call_ended

        # Mix of success and failure
        for i in range(10):
            success = i % 2 == 0  # 50% failure rate
            tool_call_started.send("test", tool_name="TestTool", query=f"q{i}", start_time=datetime.now())
            tool_call_ended.send("test", tool_name="TestTool", query=f"q{i}", end_time=datetime.now(), duration_ms=10.0, success=success, result_count=1 if success else 0, error_type=None if success else "Error")

        text, color = collector._derive_circuit_state(collector._stats["TestTool"].to_dict())
        assert "Recovering" in text
        assert color == "yellow"
