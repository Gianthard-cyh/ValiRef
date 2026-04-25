"""Tool call monitoring using blinker signals."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Any, Callable, TYPE_CHECKING
from datetime import datetime, timedelta
from collections import deque
from blinker import signal
import threading
import time

if TYPE_CHECKING:
    from rich.table import Table

# Define signals
tool_call_started = signal("tool-call-started")
tool_call_ended = signal("tool-call-ended")

# Constants for cleanup
ACTIVE_CALL_MAX_AGE_SECONDS = 300  # 5 minutes


@dataclass
class ToolStats:
    """Tool statistics aggregation."""

    tool_name: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_duration_ms: float = 0.0
    max_duration_ms: float = 0.0
    min_duration_ms: float = float("inf")
    total_results: int = 0
    errors: Dict[str, int] = field(default_factory=dict)
    active_tasks: int = 0
    _call_history: deque = field(default_factory=lambda: deque(maxlen=1000))

    @property
    def avg_duration_ms(self) -> float:
        return self.total_duration_ms / self.total_calls if self.total_calls else 0

    @property
    def avg_results(self) -> float:
        return self.total_results / self.total_calls if self.total_calls else 0

    @property
    def calls_per_minute(self) -> float:
        """Calculate calls per minute based on call history."""
        now = datetime.now()
        cutoff = now - timedelta(seconds=60)
        # Count calls in the last 60 seconds
        recent_calls = sum(1 for t in self._call_history if t > cutoff)
        return recent_calls

    def record_call(self):
        """Record a call timestamp for rate calculation."""
        self._call_history.append(datetime.now())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "avg_duration_ms": round(self.avg_duration_ms, 2),
            "max_duration_ms": round(self.max_duration_ms, 2),
            "min_duration_ms": round(self.min_duration_ms, 2)
            if self.min_duration_ms != float("inf")
            else 0,
            "avg_results": round(self.avg_results, 2),
            "errors": self.errors,
            "active_tasks": self.active_tasks,
            "calls_per_minute": round(self.calls_per_minute, 1),
        }


# Circuit breaker state display mapping
CIRCUIT_STATE_DISPLAY = {
    "CLOSED": ("Normal", "green"),
    "HALF_OPEN": ("Recovering", "yellow"),
    "OPEN": ("Open", "red"),
}


def format_circuit_state(state: str) -> tuple[str, str]:
    """Format circuit breaker state for display."""
    return CIRCUIT_STATE_DISPLAY.get(state, (state, "white"))


class ToolMetricsCollector:
    """Tool metrics collector - signal-based state tracking without tool instance references."""

    def __init__(self, on_update: Optional[Callable] = None):
        self._lock = threading.Lock()
        self._stats: Dict[str, ToolStats] = {}
        self._active_calls: Dict[str, dict] = {}
        self._on_update = on_update
        self._last_cleanup = time.time()

        # Auto-subscribe to signals
        tool_call_started.connect(self._on_started)
        tool_call_ended.connect(self._on_ended)

    def _cleanup_stale_calls(self):
        """Remove stale active calls that haven't completed within the max age."""
        now = time.time()
        # Only run cleanup every 60 seconds to avoid overhead
        if now - self._last_cleanup < 60:
            return

        cutoff = now - ACTIVE_CALL_MAX_AGE_SECONDS
        stale_queries = [
            query for query, data in self._active_calls.items()
            if data.get("start_time", now) < cutoff
        ]
        for query in stale_queries:
            self._active_calls.pop(query, None)
            # Also decrement active_tasks for the tool
            tool_name = self._active_calls.get(query, {}).get("tool_name")
            if tool_name and tool_name in self._stats:
                self._stats[tool_name].active_tasks = max(
                    0, self._stats[tool_name].active_tasks - 1
                )
        self._last_cleanup = now

    def _on_started(self, sender, **kwargs):
        """Handle call start signal - increment active count."""
        tool_name = kwargs["tool_name"]
        query = kwargs["query"]

        with self._lock:
            self._cleanup_stale_calls()

            stats = self._stats.get(tool_name)
            if stats is None:
                stats = ToolStats(tool_name=tool_name)
                self._stats[tool_name] = stats

            stats.active_tasks += 1
            self._active_calls[query] = {
                "tool_name": tool_name,
                "start_time": time.time(),
            }

        if self._on_update:
            self._on_update()

    def _on_ended(self, sender, **kwargs):
        """Handle call end signal - decrement active count and update stats."""
        tool_name = kwargs["tool_name"]
        query = kwargs["query"]

        with self._lock:
            stats = self._stats.get(tool_name)
            if stats is None:
                stats = ToolStats(tool_name=tool_name)
                self._stats[tool_name] = stats

            stats.total_calls += 1
            stats.record_call()

            if kwargs.get("success"):
                stats.successful_calls += 1
            else:
                stats.failed_calls += 1
                error_type = kwargs.get("error_type")
                if error_type:
                    stats.errors[error_type] = stats.errors.get(error_type, 0) + 1

            duration = kwargs.get("duration_ms", 0)
            stats.total_duration_ms += duration
            stats.max_duration_ms = max(stats.max_duration_ms, duration)
            stats.min_duration_ms = min(stats.min_duration_ms, duration)
            stats.total_results += kwargs.get("result_count", 0)

            stats.active_tasks = max(0, stats.active_tasks - 1)
            self._active_calls.pop(query, None)

        if self._on_update:
            self._on_update()

    def get_summary(self) -> Dict[str, Any]:
        """Get statistics summary."""
        with self._lock:
            total_calls = sum(s.total_calls for s in self._stats.values())
            successful = sum(s.successful_calls for s in self._stats.values())

            return {
                "total_calls": total_calls,
                "successful_calls": successful,
                "failed_calls": sum(s.failed_calls for s in self._stats.values()),
                "success_rate": round(successful / total_calls, 4)
                if total_calls
                else 0,
                "avg_duration_ms": round(
                    sum(s.total_duration_ms for s in self._stats.values())
                    / total_calls,
                    2,
                )
                if total_calls
                else 0,
                "by_tool": {name: s.to_dict() for name, s in self._stats.items()},
            }

    def get_stats_table(self) -> "Table":
        """Generate Rich table for Live display."""
        from rich.table import Table
        from rich import box

        stats = self.get_summary()
        if stats["total_calls"] == 0:
            return Table(title="Tool Metrics - No data yet", box=box.ROUNDED)

        table = Table(title="Tool API Call Statistics", box=box.ROUNDED)
        table.add_column("Tool", style="cyan")
        table.add_column("Calls", justify="right")
        table.add_column("Success", justify="right", style="green")
        table.add_column("Failed", justify="right", style="red")
        table.add_column("Avg Time", justify="right")
        table.add_column("Status", justify="center")
        table.add_column("Active", justify="right")
        table.add_column("Rate", justify="right")

        for tool_name, tool_stats in stats["by_tool"].items():
            circuit_display, circuit_style = self._derive_circuit_state(tool_stats)

            active = tool_stats.get("active_tasks", 0)
            active_display = f"[yellow]{active}[/yellow]" if active > 0 else str(active)

            rate = tool_stats.get("calls_per_minute", 0)
            rate_display = f"{rate:.1f}/min" if rate > 0 else "-"

            table.add_row(
                tool_name,
                str(tool_stats["total_calls"]),
                str(tool_stats["successful_calls"]),
                str(tool_stats["failed_calls"]),
                f"{tool_stats['avg_duration_ms']:.0f}ms",
                f"[{circuit_style}]{circuit_display}[/{circuit_style}]",
                active_display,
                rate_display,
            )

        table.add_row(
            "[bold]Total[/bold]",
            f"[bold]{stats['total_calls']}[/bold]",
            f"[bold]{stats['successful_calls']}[/bold]",
            f"[bold]{stats['failed_calls']}[/bold]",
            f"[bold]{stats['avg_duration_ms']:.0f}ms[/bold]",
            "",
            "",
            "",
            style="dim",
        )

        return table

    def _derive_circuit_state(self, tool_stats: Dict[str, Any]) -> tuple[str, str]:
        """Derive circuit breaker state from stats for display.

        Since we track purely via signals without tool instance access,
        we derive state from recent error patterns.
        """
        total = tool_stats.get("total_calls", 0)
        failed = tool_stats.get("failed_calls", 0)

        if total == 0:
            return format_circuit_state("CLOSED")

        error_rate = failed / total if total > 0 else 0

        if error_rate > 0.5 and total >= 3:
            return format_circuit_state("OPEN")
        elif error_rate > 0.2 and total >= 2:
            return format_circuit_state("HALF_OPEN")
        else:
            return format_circuit_state("CLOSED")

    def reset(self):
        """Reset statistics."""
        with self._lock:
            self._stats.clear()
            self._active_calls.clear()
