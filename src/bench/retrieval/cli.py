"""CLI for retrieval evaluation."""
import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich import box

from .evaluator import RetrievalEvaluator, RetrievalEvalResult

console = Console()


def evaluate(
    dataset_path: str = typer.Argument(..., help="Path to the CSV dataset file"),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file for metrics (JSON)"
    ),
    queries_output: Optional[str] = typer.Option(
        None, "--queries-output", "-q", help="Export all queries to file (JSON/CSV)"
    ),
    queries_format: str = typer.Option(
        "json", "--queries-format", "-f", help="Format for queries export: json or csv"
    ),
    limit: Optional[int] = typer.Option(
        None, "--limit", "-l", help="Limit number of samples to test"
    ),
    workers: int = typer.Option(
        5, "--workers", "-w", help="Number of concurrent workers"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output"
    ),
):
    """
    Evaluate local retrieval subsystem (BM25 + CrossEncoder).

    This command runs the detector on benchmark samples and records all
    search queries to evaluate retrieval performance (Recall@K, MRR).

    Examples:
        # Basic evaluation
        uv run python -m src.bench.retrieval.cli data/dataset.csv

        # Export all queries for later analysis
        uv run python -m src.bench.retrieval.cli data/dataset.csv -q queries.json

        # Limit to 50 samples with 10 concurrent workers
        uv run python -m src.bench.retrieval.cli data/dataset.csv -l 50 -w 10
    """
    path = Path(dataset_path)
    if not path.exists():
        console.print(f"[bold red]Error:[/bold red] Dataset not found: {dataset_path}")
        raise typer.Exit(code=1)

    async def run():
        evaluator = RetrievalEvaluator()
        return await evaluator.evaluate(
            dataset_path=str(path),
            sample_size=limit or 100,
            workers=workers,
            verbose=verbose,
        )

    try:
        result = asyncio.run(run())

        # Print metrics table
        _print_metrics(result)

        # Save metrics to file
        if output:
            import json
            output_path = Path(output)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result.to_dict(), f, indent=2)
            console.print(f"\n[green]Metrics saved to:[/green] {output_path}")

        # Export all queries
        if queries_output and result.all_records:
            result.export_queries(queries_output, queries_format)
            console.print(f"[green]Queries exported to:[/green] {queries_output}")

    except KeyboardInterrupt:
        console.print("\n[bold yellow]Evaluation interrupted[/bold yellow]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Evaluation failed:[/bold red] {str(e)}")
        raise typer.Exit(code=1)


def _print_metrics(result: RetrievalEvalResult):
    """Print retrieval metrics in a nice table."""
    table = Table(title="Retrieval Performance Metrics", box=box.ROUNDED)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="green")

    table.add_row("Total Samples", str(result.total_samples))
    table.add_row("Total Queries", str(result.total_queries))
    table.add_row("", "")  # Spacer
    table.add_row("Recall@1", f"{result.recall_at_1:.2%}")
    table.add_row("Recall@3", f"{result.recall_at_3:.2%}")
    table.add_row("Recall@5", f"{result.recall_at_5:.2%}")
    table.add_row("", "")
    table.add_row("MRR (Mean Reciprocal Rank)", f"{result.mrr:.4f}")

    console.print(table)


if __name__ == "__main__":
    typer.run(evaluate)
