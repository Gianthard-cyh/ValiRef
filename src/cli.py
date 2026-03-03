import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import box
from src.core.pipeline import ValidationPipeline
from src.core.detector import HallucinationDetector
from src.bench import BenchmarkRunner
from src.cli_callbacks import CliCallback
import logging
import asyncio
import json

app = typer.Typer(
    name="valiref",
    help="ValiRef: A tool for validating references in PDF documents.",
    add_completion=False,
)
console = Console()


@app.command()
def validate(
    pdf_path: str = typer.Argument(..., help="Path to the PDF file to validate"),
    max_workers: int = typer.Option(
        5, "--workers", "-w", help="Number of concurrent validation threads"
    ),
    output_json: bool = typer.Option(
        False, "--json", help="Output results in JSON format"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose logging output"
    ),
    show_metrics: bool = typer.Option(
        True, "--metrics/--no-metrics", help="Show real-time tool metrics"
    ),
):
    """
    Validate references in a PDF file.
    """
    # Adjust logging level based on verbose flag
    if not verbose:
        # Suppress all logs in non-verbose mode to keep the progress bar clean
        # We rely on RichConsoleCallback to show progress and errors
        logging.getLogger("valiref").setLevel(logging.CRITICAL)
        logging.getLogger("httpx").setLevel(logging.CRITICAL)
        logging.getLogger("httpcore").setLevel(logging.CRITICAL)
        logging.getLogger().setLevel(logging.CRITICAL)
    else:
        logging.getLogger("valiref").setLevel(logging.INFO)
        logging.getLogger().setLevel(logging.INFO)

    path = Path(pdf_path)
    if not path.exists():
        console.print(f"[bold red]Error:[/bold red] File not found: {pdf_path}")
        raise typer.Exit(code=1)

    async def run_pipeline():
        callback = CliCallback(console, show_metrics=show_metrics) if not verbose else None
        pipeline = ValidationPipeline(
            callbacks=[callback] if callback else []
        )
        if verbose:
            console.print(
                f"[bold green]Starting validation for:[/bold green] {path.name}"
            )

        return await pipeline.process_pdf(str(path), max_workers=max_workers)

    try:
        results = asyncio.run(run_pipeline())

        # 添加工具统计到结果（如果有callback且启用了metrics）
        if 'callback' in dir() and callback and callback.metrics:
            results["tool_stats"] = callback.metrics.get_summary()

        if output_json:
            console.print(json.dumps(results, indent=2))
        else:
            _print_results(results)

    except KeyboardInterrupt:
        console.print("\n[bold yellow]Operation interrupted by user[/bold yellow]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]An error occurred:[/bold red] {str(e)}")
        raise typer.Exit(code=1)


def _print_results(results: dict):
    """
    Print validation results in a nice table format.
    """
    console.print(
        f"\n[bold]Validation Summary for {results.get('file', 'Unknown')}[/bold]"
    )
    console.print(f"Total References: {results.get('references_count', 0)}")
    console.print(f"Validated: {results.get('validated_count', 0)}")
    console.print(f"Duration: {results.get('duration_seconds', 0):.2f}s")

    console.print("\n[bold]Detailed Report[/bold]")

    for i, item in enumerate(results.get("results", []), 1):
        paper = item.get("paper", {})
        title = paper.get("title", "Unknown Title")
        authors_list = paper.get("authors", [])
        if isinstance(authors_list, list):
            authors = ", ".join(authors_list)
        else:
            authors = str(authors_list)

        validation = item.get("validation", {})
        # Handle cases where validation might be None or empty
        if not validation:
            is_hallucination = None
            confidence = 0.0
            reasoning = "Validation failed or not performed."
            evidence = []
        else:
            is_hallucination = validation.get("is_hallucination")
            confidence = validation.get("confidence", 0.0)
            reasoning = validation.get("reasoning", "No reasoning provided.")
            evidence = validation.get("evidence", [])

        # Color coding and Status
        if is_hallucination is True:
            border_style = "red"
            status_text = "[bold red]HALLUCINATION[/bold red]"
            icon = "❌"
        elif is_hallucination is False:
            border_style = "green"
            status_text = "[bold green]REAL REFERENCE[/bold green]"
            icon = "✅"
        else:
            border_style = "yellow"
            status_text = "[bold yellow]UNKNOWN / ERROR[/bold yellow]"
            icon = "⚠️"

        content = Text()
        content.append(f"Title: {title}\n", style="bold")
        if authors:
            content.append(f"Authors: {authors}\n", style="italic")
        content.append(f"Confidence: {confidence:.2f}\n")

        content.append("\nReasoning:\n", style="bold underline")
        content.append(f"{reasoning}\n")

        if evidence:
            content.append("\nEvidence / Sources:\n", style="bold underline")
            for item in evidence:
                item_str = str(item)
                if item_str.startswith("http"):
                    content.append(f"- {item_str}\n", style="blue link " + item_str)
                else:
                    content.append(f"- {item_str}\n")
        else:
            if is_hallucination is False:
                content.append("\nEvidence / Sources:\n", style="bold underline")
                content.append(
                    "No direct link found, but verified as real.\n", style="dim"
                )
            elif is_hallucination is True:
                content.append("\nEvidence / Sources:\n", style="bold underline")
                content.append(
                    "No supporting evidence found (expected for hallucinations).\n",
                    style="dim",
                )

        panel = Panel(
            content,
            title=f"{icon} Reference #{i} - {status_text}",
            border_style=border_style,
            expand=False,
            box=box.ROUNDED,
        )
        console.print(panel)
        console.print("")  # Add spacing


@app.command()
def version():
    """
    Show the version of ValiRef.
    """
    console.print("ValiRef v0.1.0")


@app.command()
def benchmark(
    dataset_path: str = typer.Argument(..., help="Path to the CSV dataset file"),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file for results (JSON)"
    ),
    workers: int = typer.Option(
        5, "--workers", "-w", help="Number of concurrent workers"
    ),
    limit: Optional[int] = typer.Option(
        None, "--limit", "-l", help="Limit number of samples to test"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose output"
    ),
):
    """
    Run benchmark on a dataset to evaluate hallucination detection performance.
    """
    path = Path(dataset_path)
    if not path.exists():
        console.print(
            f"[bold red]Error:[/bold red] Dataset file not found: {dataset_path}"
        )
        raise typer.Exit(code=1)

    # Adjust logging level
    if not verbose:
        logging.getLogger("valiref").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)

    async def run_benchmark():
        detector = HallucinationDetector()
        runner = BenchmarkRunner(detector)

        if verbose:
            console.print(
                f"[bold green]Starting benchmark with {workers} workers...[/bold green]"
            )

        return await runner.run(
            dataset_path=str(path),
            max_workers=workers,
            limit=limit,
            verbose=True,  # Always show progress bar for benchmark
        )

    try:
        result = asyncio.run(run_benchmark())

        # Print results
        runner = BenchmarkRunner(HallucinationDetector())
        runner.print_results(result)

        # Save to file if output specified
        if output:
            output_path = Path(output)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result.to_dict(), f, indent=2)
            console.print(f"\n[green]Results saved to:[/green] {output_path}")

    except KeyboardInterrupt:
        console.print("\n[bold yellow]Benchmark interrupted by user[/bold yellow]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Benchmark failed:[/bold red] {str(e)}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
