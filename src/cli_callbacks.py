from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskID, TimeRemainingColumn
from src.core.callbacks import ValidationCallback
from src.bench.schema import Paper

class CliCallback(ValidationCallback):
    def __init__(self, console: Console):
        self.console = console
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=console,
            transient=True
        )
        self.extraction_task: Optional[TaskID] = None
        self.validation_task: Optional[TaskID] = None

    def on_extraction_start(self, filename: str):
        self.progress.start()
        self.extraction_task = self.progress.add_task(f"Extracting references from {filename}...", total=None)

    def on_extraction_end(self, references: List[Paper]):
        if self.extraction_task is not None:
            self.progress.update(self.extraction_task, completed=1, total=1, visible=False)
        self.console.print(f"[green]✓[/green] Extracted {len(references)} references.")

    def on_validation_start(self, total_references: int):
        self.validation_task = self.progress.add_task("Validating references...", total=total_references)

    def on_reference_validation_end(self, paper: Paper, result: Dict[str, Any]):
        if self.validation_task is not None:
            self.progress.advance(self.validation_task)
            
    def on_reference_validation_error(self, paper: Paper, error: Exception):
        # Print error above the progress bar
        self.progress.console.print(f"[red]Error validating '{paper.title[:30]}...': {error}[/red]")
        if self.validation_task is not None:
            self.progress.advance(self.validation_task)

    def on_pipeline_end(self, results: Dict[str, Any]):
        self.progress.stop()

    def on_error(self, error: Exception):
        self.progress.stop()
        self.console.print(f"[bold red]Pipeline Error:[/bold red] {error}")
