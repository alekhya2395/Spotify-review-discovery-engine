"""Phase 1 CLI entry point.

Examples:
    python run_phase1.py                       # run all sources
    python run_phase1.py --source play_store   # one source
    python run_phase1.py --source play_store --source reddit
    python run_phase1.py --list                # show available sources
"""

from __future__ import annotations

import json
from typing import List, Optional

import typer
from rich.console import Console
from rich.table import Table

from src.phase1_collection import CollectionPipeline, SourceType

app = typer.Typer(add_completion=False, help="Phase 1 — Spotify Review Collection")
console = Console()


@app.command()
def main(
    source: Optional[List[str]] = typer.Option(
        None,
        "--source",
        "-s",
        help="Source to run. Repeat for multiple. Defaults to all.",
    ),
    list_sources: bool = typer.Option(
        False, "--list", "-l", help="List available sources and exit."
    ),
    json_summary: bool = typer.Option(
        False, "--json", help="Print the run summary as JSON instead of a table."
    ),
) -> None:
    """Run the Phase 1 data collection pipeline."""

    if list_sources:
        table = Table(title="Available sources")
        table.add_column("Key", style="cyan")
        for s in SourceType:
            table.add_row(s.value)
        console.print(table)
        raise typer.Exit(0)

    selected: Optional[List[SourceType]] = None
    if source:
        try:
            selected = [SourceType(s) for s in source]
        except ValueError as exc:
            console.print(f"[red]Invalid source:[/red] {exc}")
            raise typer.Exit(2)

    pipeline = CollectionPipeline(sources=selected)
    summary = pipeline.run()
    payload = CollectionPipeline.summary_to_dict(summary)

    if json_summary:
        console.print_json(json.dumps(payload, default=str))
        return

    table = Table(title="Phase 1 — Collection Summary")
    table.add_column("Source", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Records In", justify="right")
    table.add_column("Records Written", justify="right")
    table.add_column("Duplicates", justify="right")
    table.add_column("Path / Error")

    for src, info in payload["per_source"].items():
        if info.get("status") == "ok":
            table.add_row(
                src,
                "[green]ok[/green]",
                str(info.get("records_in", 0)),
                str(info.get("records_written", 0)),
                str(info.get("duplicates_dropped", 0)),
                str(info.get("parquet_path", "")),
            )
        else:
            table.add_row(
                src,
                "[red]error[/red]",
                "-",
                "-",
                "-",
                str(info.get("error", "")),
            )

    console.print(table)
    console.print(
        f"[bold]Total written:[/bold] {payload['total_records']}  "
        f"[bold]Failures:[/bold] {payload['total_failures']}  "
        f"[dim]Duration:[/dim] {payload['duration_seconds']:.1f}s"
    )


if __name__ == "__main__":
    app()
