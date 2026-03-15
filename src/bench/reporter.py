"""Benchmark results reporter."""
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.bench.metrics.dataclasses import BenchmarkResult


class BenchmarkReporter:
    """Reporter for printing benchmark results."""

    def __init__(self, console: Console = None):
        self.console = console or Console()

    def print_results(self, result: BenchmarkResult):
        """Print benchmark results in a formatted table."""
        self.console.print("\n[bold]Benchmark Results[/bold]\n")

        # Per-class metrics table
        mc = result.metrics
        class_table = Table(
            title="Per-Class Metrics",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta",
        )
        class_table.add_column("Class", style="cyan")
        class_table.add_column("Precision", justify="right")
        class_table.add_column("Recall", justify="right")
        class_table.add_column("F1", justify="right")
        class_table.add_column("Support", justify="right")

        for c in ['Real', 'Fabrication', 'AttributionError', 'Irrelevance', 'Counterfactual']:
            style = "green" if c == "Real" else "yellow"
            support = mc.per_class_support.get(c, 0)
            if support > 0:  # Only show classes that appear in the dataset
                class_table.add_row(
                    f"[{style}]{c}[/{style}]",
                    f"{mc.per_class_precision.get(c, 0):.4f}",
                    f"{mc.per_class_recall.get(c, 0):.4f}",
                    f"{mc.per_class_f1.get(c, 0):.4f}",
                    str(support),
                )

        self.console.print(class_table)
        self.console.print()

        # Confusion matrix table
        cm = mc.confusion_matrix
        confusion_table = Table(
            title="Confusion Matrix (Ground Truth → Predicted)",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta",
        )
        confusion_table.add_column("GT \\ Pred", style="cyan")
        for c in ['Real', 'Fabrication', 'AttributionError', 'Irrelevance', 'Counterfactual']:
            confusion_table.add_column(c[:8], justify="right")  # Shortened names for display

        for true_c in ['Real', 'Fabrication', 'AttributionError', 'Irrelevance', 'Counterfactual']:
            row = [f"[bold]{true_c[:8]}[/bold]"]
            for pred_c in ['Real', 'Fabrication', 'AttributionError', 'Irrelevance', 'Counterfactual']:
                count = cm.get(true_c, {}).get(pred_c, 0)
                # Highlight diagonal (correct predictions)
                if true_c == pred_c:
                    row.append(f"[green]{count}[/green]" if count > 0 else "0")
                else:
                    row.append(f"[red]{count}[/red]" if count > 0 else "0")
            confusion_table.add_row(*row)

        self.console.print(confusion_table)
        self.console.print()

        # Average metrics summary
        avg_table = Table(
            title="Average Metrics",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta",
        )
        avg_table.add_column("Average Type", style="cyan")
        avg_table.add_column("Precision", justify="right")
        avg_table.add_column("Recall", justify="right")
        avg_table.add_column("F1", justify="right")
        avg_table.add_column("Accuracy", justify="right")

        avg_table.add_row(
            "Macro",
            f"{mc.macro_precision:.4f}",
            f"{mc.macro_recall:.4f}",
            f"{mc.macro_f1:.4f}",
            "-"
        )
        avg_table.add_row(
            "Micro",
            f"{mc.micro_precision:.4f}",
            f"{mc.micro_recall:.4f}",
            f"{mc.micro_f1:.4f}",
            f"{mc.accuracy:.4f}"
        )
        avg_table.add_row(
            "Weighted",
            f"{mc.weighted_precision:.4f}",
            f"{mc.weighted_recall:.4f}",
            f"{mc.weighted_f1:.4f}",
            "-"
        )

        self.console.print(avg_table)
        self.console.print()

        # Summary panel
        correct = sum(1 for s in result.samples if s.correct)
        total = len(result.samples)
        accuracy_pct = (correct / total * 100) if total > 0 else 0

        summary_text = (
            f"Correctly classified: {correct}/{total} ({accuracy_pct:.1f}%)\n"
            f"Duration: {result.duration_seconds:.2f}s\n"
            f"Throughput: {total / result.duration_seconds:.2f} samples/sec"
        )

        self.console.print(
            Panel(
                summary_text,
                title="Summary",
                border_style="blue",
                box=box.ROUNDED,
            )
        )


def print_results(result: BenchmarkResult, console: Console = None):
    """Convenience function to print benchmark results."""
    reporter = BenchmarkReporter(console)
    reporter.print_results(result)
