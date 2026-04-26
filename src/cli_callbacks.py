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
from src.core.callbacks import ValidationCallback
from src.core.tool_monitor import ToolMetricsCollector
from src.bench.schema import Paper, Reference
from src.core.state import PipelineState, ValidationPhase


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

    async def on_pipeline_start(self, filename: str):
        if self.show_metrics:
            self.metrics = ToolMetricsCollector(on_update=self._on_metrics_update)
            self.live = Live(
                self.metrics.get_stats_table(),
                console=self.console,
                refresh_per_second=2,
                transient=True,
            )
            self.live.start()

        self.progress.start()
        self.extraction_task = self.progress.add_task(
            f"Extracting references from {filename}...", total=None
        )

    def _on_metrics_update(self):
        if self.live and self.metrics:
            self.live.update(self.metrics.get_stats_table())

    async def on_extraction_end(self, references: List[Paper]):
        if self.extraction_task is not None:
            self.progress.update(
                self.extraction_task, completed=1, total=1, visible=False
            )
        self.console.print(f"Extracted {len(references)} references.")

    async def on_reference_validation_end(self, paper: Paper, result: Dict[str, Any]):
        if self.validation_task is not None:
            self.progress.advance(self.validation_task)

    async def on_reference_validation_error(self, paper: Paper, error: Exception):
        self.progress.console.print(
            f"[red]Error validating '{paper.title[:30]}...': {error}[/red]"
        )
        if self.validation_task is not None:
            self.progress.advance(self.validation_task)

    async def on_pipeline_end(self, results: Dict[str, Any]):
        self.progress.stop()

        if self.live:
            self.live.stop()
            self.live = None

        if self.metrics and self.show_metrics:
            self.console.print()
            self.console.print(self.metrics.get_stats_table())

    async def on_error(self, error: Exception):
        self.progress.stop()
        if self.live:
            self.live.stop()
        self.console.print(f"[bold red]Pipeline Error:[/bold red] {error}")

    async def on_phase_change(self, state: PipelineState):
        if state.phase == ValidationPhase.EXTRACTION:
            pass
        elif state.phase == ValidationPhase.DETECTION:
            if self.extraction_task is not None:
                self.progress.update(
                    self.extraction_task, completed=1, total=1, visible=False
                )
            self.console.print(f"[green]✓[/green] Extracted {state.extraction_found} references")
            self.validation_task = self.progress.add_task(
                f"Validating {state.detection_total} references...", total=state.detection_total
            )
        elif state.phase == ValidationPhase.ERROR:
            self.progress.stop()
            if self.live:
                self.live.stop()

    async def on_extraction_progress(self, state: PipelineState, new_refs: List[Reference]):
        if self.extraction_task is not None:
            self.progress.update(
                self.extraction_task,
                description=f"Extracting references... {state.extraction_found} found"
            )
        for ref in new_refs:
            if ref.title:
                self.console.print(f"  [dim]• {ref.title[:60]}...[/dim]")
