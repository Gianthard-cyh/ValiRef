from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.live import Live
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskID,
    TimeRemainingColumn,
)
from rich import box
from src.core.callbacks import ValidationCallback
from src.core.tool_monitor import ToolMetricsCollector
from src.bench.schema import Paper


class CliCallback(ValidationCallback):
    def __init__(self, console: Console, show_metrics: bool = True):
        self.console = console
        self.show_metrics = show_metrics
        self.metrics: Optional[ToolMetricsCollector] = None
        self.live: Optional[Live] = None

        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=console,
            transient=True,
        )
        self.extraction_task: Optional[TaskID] = None
        self.validation_task: Optional[TaskID] = None

    def on_pipeline_start(self, filename: str):
        """启动Live显示和进度条"""
        if self.show_metrics:
            # Create metrics collector without tool instances (signal-based tracking)
            self.metrics = ToolMetricsCollector(
                on_update=self._on_metrics_update
            )
            # 启动Live显示工具统计
            self.live = Live(
                self.metrics.get_stats_table(),
                console=self.console,
                refresh_per_second=2,
                transient=True
            )
            self.live.start()

        self.progress.start()
        self.extraction_task = self.progress.add_task(
            f"Extracting references from {filename}...", total=None
        )

    def _on_metrics_update(self):
        """指标更新时刷新Live"""
        if self.live and self.metrics:
            self.live.update(self.metrics.get_stats_table())

    def on_extraction_end(self, references: List[Paper]):
        if self.extraction_task is not None:
            self.progress.update(
                self.extraction_task, completed=1, total=1, visible=False
            )
        self.console.print(f"Extracted {len(references)} references.")

    def on_validation_start(self, total_references: int):
        self.validation_task = self.progress.add_task(
            "Validating references...", total=total_references
        )

    def on_reference_validation_end(self, paper: Paper, result: Dict[str, Any]):
        if self.validation_task is not None:
            self.progress.advance(self.validation_task)

    def on_reference_validation_error(self, paper: Paper, error: Exception):
        # Print error above the progress bar
        self.progress.console.print(
            f"[red]Error validating '{paper.title[:30]}...': {error}[/red]"
        )
        if self.validation_task is not None:
            self.progress.advance(self.validation_task)

    def on_pipeline_end(self, results: Dict[str, Any]):
        """清理并显示最终统计"""
        # 停止进度条
        self.progress.stop()

        # 停止Live
        if self.live:
            self.live.stop()
            self.live = None

        # 显示最终统计表格
        if self.metrics and self.show_metrics:
            self.console.print()  # 空行
            self.console.print(self.metrics.get_stats_table())

    def on_error(self, error: Exception):
        self.progress.stop()
        if self.live:
            self.live.stop()
        self.console.print(f"[bold red]Pipeline Error:[/bold red] {error}")
