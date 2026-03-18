import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import box
from rich.table import Table
from langchain_deepseek import ChatDeepSeek

from src.core.pipeline import ValidationPipeline
from src.core.detector import HallucinationDetector
from src.core.extract import PDFExtractor, TextExtractor
from src.core.tools import AggregateSearchFactory
from src.core.config import (
    DEEPSEEK_API_KEY,
    LLM_MODEL,
    LLM_TEMPERATURE,
    DETECTOR_TEMPERATURE,
    LLM_MAX_TOKENS,
    LLM_TIMEOUT,
    LLM_MAX_RETRIES,
)
from src.core.search_cache import get_cache, clear_cache
from src.bench import BenchmarkRunner, print_results
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


def create_llm(temperature: Optional[float] = None) -> ChatDeepSeek:
    """Factory function to create a ChatDeepSeek LLM instance."""
    if DEEPSEEK_API_KEY is None:
        raise ValueError("DEEPSEEK_API_KEY is not set")

    return ChatDeepSeek(
        model=LLM_MODEL,
        temperature=temperature if temperature is not None else LLM_TEMPERATURE,
        max_tokens=LLM_MAX_TOKENS,
        timeout=LLM_TIMEOUT,
        max_retries=LLM_MAX_RETRIES,
        api_key=DEEPSEEK_API_KEY,
    )


def create_detector(
    llm: Optional[ChatDeepSeek] = None,
    search_mode: str = "local",
) -> HallucinationDetector:
    """Factory function to create a HallucinationDetector with all dependencies."""
    llm_instance = (
        llm if llm is not None else create_llm(temperature=DETECTOR_TEMPERATURE)
    )
    aggregate_search = AggregateSearchFactory.create(search_mode)
    return HallucinationDetector(llm=llm_instance, search=aggregate_search)


def create_pipeline(
    callbacks: Optional[list] = None,
    search_mode: str = "local",
) -> ValidationPipeline:
    """Factory function to create a ValidationPipeline with all dependencies."""
    llm = create_llm()
    text_extractor = TextExtractor(llm=llm)
    pdf_extractor = PDFExtractor(text_extractor=text_extractor)
    detector = create_detector(llm=llm, search_mode=search_mode)

    return ValidationPipeline(
        extractor=pdf_extractor,
        detector=detector,
        callbacks=callbacks or [],
    )


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
    search_mode: str = typer.Option(
        "local",
        "--search-mode",
        "-s",
        help="Search mode: 'local' (default, uses ParadeDB) or 'online' (uses external APIs)",
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
        callback = (
            CliCallback(console, show_metrics=show_metrics) if not verbose else None
        )
        pipeline = create_pipeline(
            callbacks=[callback] if callback else [],
            search_mode=search_mode,
        )
        if verbose:
            console.print(
                f"[bold green]Starting validation for:[/bold green] {path.name}"
            )
            console.print(f"[bold blue]Search mode:[/bold blue] {search_mode}")

        return await pipeline.process_pdf(str(path), max_workers=max_workers)

    try:
        results = asyncio.run(run_pipeline())

        # 添加工具统计到结果（如果有callback且启用了metrics）
        if "callback" in dir() and callback and callback.metrics:
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
            icon = "[X]"
        elif is_hallucination is False:
            border_style = "green"
            status_text = "[bold green]REAL REFERENCE[/bold green]"
            icon = "[OK]"
        else:
            border_style = "yellow"
            status_text = "[bold yellow]UNKNOWN / ERROR[/bold yellow]"
            icon = "[?]"

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
    show_metrics: bool = typer.Option(
        True, "--metrics/--no-metrics", help="Show real-time tool call metrics"
    ),
    search_mode: str = typer.Option(
        "local",
        "--search-mode",
        "-s",
        help="Search mode: 'local' (default, uses ParadeDB) or 'online' (uses external APIs)",
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

    # Adjust logging level based on verbose flag
    if not verbose:
        # Suppress all logs in non-verbose mode to keep the progress bar clean
        logging.getLogger("valiref").setLevel(logging.CRITICAL)
        logging.getLogger("httpx").setLevel(logging.CRITICAL)
        logging.getLogger("httpcore").setLevel(logging.CRITICAL)
        logging.getLogger().setLevel(logging.CRITICAL)
    else:
        logging.getLogger("valiref").setLevel(logging.INFO)
        logging.getLogger().setLevel(logging.INFO)

    async def run_benchmark():
        detector = create_detector(search_mode=search_mode)
        runner = BenchmarkRunner(detector)

        if verbose:
            console.print(
                f"[bold green]Starting benchmark with {workers} workers...[/bold green]"
            )
            console.print(f"[bold blue]Search mode:[/bold blue] {search_mode}")

        return await runner.run(
            dataset_path=str(path),
            max_workers=workers,
            limit=limit,
            verbose=True,  # Always show progress bar for benchmark
            show_metrics=show_metrics,
        )

    try:
        result = asyncio.run(run_benchmark())

        # Print results
        print_results(result)

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


@app.command()
def cache(
    action: str = typer.Argument(
        ..., help="Action to perform: 'clear', 'stats', or 'show'"
    ),
):
    """
    Manage search result cache.

    Actions:
        clear: Remove all cached search results
        stats: Show cache statistics
        show: Display cache file location
    """
    cache_instance = get_cache()

    if action == "clear":
        clear_cache()
        console.print("[green]Search cache cleared successfully.[/green]")

    elif action == "stats":
        stats = cache_instance.get_stats()
        table = Table(title="Cache Statistics", box=box.ROUNDED)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right", style="green")

        table.add_row("Total Entries", str(stats["total_entries"]))
        table.add_row("Valid Entries", str(stats["valid_entries"]))
        table.add_row("Expired Entries", str(stats["expired_entries"]))

        console.print(table)

    elif action == "show":
        cache_file = cache_instance.cache_file
        console.print(f"[bold]Cache location:[/bold] {cache_file}")
        if cache_file.exists():
            size = cache_file.stat().st_size
            console.print(f"[bold]Cache size:[/bold] {size:,} bytes")
        else:
            console.print("[yellow]Cache file does not exist yet.[/yellow]")

    else:
        console.print(f"[bold red]Unknown action:[/bold red] {action}")
        console.print("Valid actions: clear, stats, show")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
