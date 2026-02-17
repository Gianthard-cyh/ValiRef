import typer
from typing import Optional
from pathlib import Path
from rich.console import Console
from rich.table import Table
from src.core.pipeline import ValidationPipeline
from src.cli_callbacks import RichConsoleCallback
import logging

# Configure logging to suppress debug output by default
# logging.basicConfig(level=logging.INFO) # Removed to avoid conflict with internal logger configuration

app = typer.Typer(
    name="valiref",
    help="ValiRef: A tool for validating references in PDF documents.",
    add_completion=False,
)
console = Console()

@app.command()
def validate(
    pdf_path: str = typer.Argument(..., help="Path to the PDF file to validate"),
    max_workers: int = typer.Option(5, "--workers", "-w", help="Number of concurrent validation threads"),
    output_json: bool = typer.Option(False, "--json", help="Output results in JSON format"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging output"),
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

    try:
        if verbose:
            pipeline = ValidationPipeline()
            console.print(f"[bold green]Starting validation for:[/bold green] {path.name}")
            results = pipeline.process_pdf(str(path), max_workers=max_workers)
        else:
            # Use RichConsoleCallback for nice progress updates
            callback = RichConsoleCallback(console)
            pipeline = ValidationPipeline(callbacks=[callback])
            results = pipeline.process_pdf(str(path), max_workers=max_workers)
        
        if output_json:
            import json
            console.print(json.dumps(results, indent=2))
        else:
            _print_results(results)
            
    except Exception as e:
        console.print(f"[bold red]An error occurred:[/bold red] {str(e)}")
        raise typer.Exit(code=1)

def _print_results(results: dict):
    """
    Print validation results in a nice table format.
    """
    console.print(f"\n[bold]Validation Summary for {results.get('file', 'Unknown')}[/bold]")
    console.print(f"Total References: {results.get('references_count', 0)}")
    console.print(f"Validated: {results.get('validated_count', 0)}")
    console.print(f"Duration: {results.get('duration_seconds', 0):.2f}s")
    
    table = Table(title="Validation Details")
    table.add_column("Reference", style="cyan", no_wrap=True)
    table.add_column("Status", style="magenta")
    table.add_column("Is Hallucination", style="red")
    table.add_column("Confidence", style="green")
    
    for item in results.get("results", []):
        paper = item.get("paper", {})
        title = paper.get("title", "Unknown Title")
        # Truncate long titles
        if len(title) > 50:
            title = title[:47] + "..."
            
        validation = item.get("validation", {})
        status = item.get("status", "unknown")
        
        is_hallucination = str(validation.get("is_hallucination", "N/A"))
        confidence = f"{validation.get('confidence', 0.0):.2f}"
        
        table.add_row(title, status, is_hallucination, confidence)
        
    console.print(table)

@app.command()
def version():
    """
    Show the version of ValiRef.
    """
    console.print("ValiRef v0.1.0")

if __name__ == "__main__":
    app()
