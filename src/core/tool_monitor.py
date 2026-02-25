"""Tool call monitoring using blinker signals."""
from dataclasses import dataclass, field
from typing import Dict, Optional, Any, Callable
from datetime import datetime
from blinker import signal
import threading

# 定义信号
tool_call_started = signal('tool-call-started')
tool_call_ended = signal('tool-call-ended')


@dataclass
class ToolStats:
    """工具统计聚合"""
    tool_name: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_duration_ms: float = 0.0
    max_duration_ms: float = 0.0
    min_duration_ms: float = float('inf')
    total_results: int = 0
    errors: Dict[str, int] = field(default_factory=dict)

    @property
    def avg_duration_ms(self) -> float:
        return self.total_duration_ms / self.total_calls if self.total_calls else 0

    @property
    def avg_results(self) -> float:
        return self.total_results / self.total_calls if self.total_calls else 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "avg_duration_ms": round(self.avg_duration_ms, 2),
            "max_duration_ms": round(self.max_duration_ms, 2),
            "min_duration_ms": round(self.min_duration_ms, 2) if self.min_duration_ms != float('inf') else 0,
            "avg_results": round(self.avg_results, 2),
            "errors": self.errors,
        }


class ToolMetricsCollector:
    """工具指标收集器 - 自动订阅blinker信号，支持回调通知"""

    def __init__(self, on_update: Optional[Callable] = None):
        self._lock = threading.Lock()
        self._stats: Dict[str, ToolStats] = {}
        self._start_times: Dict[str, datetime] = {}
        self._on_update = on_update  # 数据更新时的回调

        # 自动订阅信号
        tool_call_started.connect(self._on_started)
        tool_call_ended.connect(self._on_ended)

    def _on_started(self, sender, **kwargs):
        """处理调用开始信号"""
        with self._lock:
            self._start_times[kwargs['query']] = kwargs['start_time']

    def _on_ended(self, sender, **kwargs):
        """处理调用结束信号，更新统计"""
        tool_name = kwargs['tool_name']
        query = kwargs['query']

        with self._lock:
            stats = self._stats.get(tool_name)
            if stats is None:
                stats = ToolStats(tool_name=tool_name)
                self._stats[tool_name] = stats

            stats.total_calls += 1
            if kwargs.get('success'):
                stats.successful_calls += 1
            else:
                stats.failed_calls += 1
                error_type = kwargs.get('error_type')
                if error_type:
                    stats.errors[error_type] = stats.errors.get(error_type, 0) + 1

            duration = kwargs.get('duration_ms', 0)
            stats.total_duration_ms += duration
            stats.max_duration_ms = max(stats.max_duration_ms, duration)
            stats.min_duration_ms = min(stats.min_duration_ms, duration)
            stats.total_results += kwargs.get('result_count', 0)

            self._start_times.pop(query, None)

        # 通知更新
        if self._on_update:
            self._on_update()

    def get_summary(self) -> Dict[str, Any]:
        """获取统计摘要"""
        with self._lock:
            total_calls = sum(s.total_calls for s in self._stats.values())
            successful = sum(s.successful_calls for s in self._stats.values())

            return {
                "total_calls": total_calls,
                "successful_calls": successful,
                "failed_calls": sum(s.failed_calls for s in self._stats.values()),
                "success_rate": round(successful / total_calls, 4) if total_calls else 0,
                "avg_duration_ms": round(
                    sum(s.total_duration_ms for s in self._stats.values()) / total_calls, 2
                ) if total_calls else 0,
                "by_tool": {name: s.to_dict() for name, s in self._stats.items()}
            }

    def get_stats_table(self) -> "Table":
        """生成Rich表格用于Live显示"""
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
        table.add_column("Avg Results", justify="right")

        for tool_name, tool_stats in stats["by_tool"].items():
            table.add_row(
                tool_name,
                str(tool_stats["total_calls"]),
                str(tool_stats["successful_calls"]),
                str(tool_stats["failed_calls"]),
                f"{tool_stats['avg_duration_ms']:.0f}ms",
                f"{tool_stats['avg_results']:.1f}",
            )

        table.add_row(
            "[bold]Total[/bold]",
            f"[bold]{stats['total_calls']}[/bold]",
            f"[bold]{stats['successful_calls']}[/bold]",
            f"[bold]{stats['failed_calls']}[/bold]",
            f"[bold]{stats['avg_duration_ms']:.0f}ms[/bold]",
            "",
            style="dim"
        )

        return table

    def reset(self):
        """重置统计"""
        with self._lock:
            self._stats.clear()
            self._start_times.clear()
