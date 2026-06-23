"""Phase 2 CLI entry point.

Examples:
    python run_phase2.py                       # analyze everything new since last run
    python run_phase2.py --max-reviews 50      # cap this run at 50 reviews
    python run_phase2.py --batch-size 5        # smaller LLM batches
    python run_phase2.py --json                # machine-readable summary
"""

from __future__ import annotations

import json
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from src.phase2_analysis import AnalysisPipeline
from src.phase2_analysis.analyzer import Analyzer
from src.phase2_analysis.groq_client import GroqClient, GroqClientError

app = typer.Typer(add_completion=False, help="Phase 2 — Spotify Review AI Analysis (Groq)")
console = Console()


@app.command()
def main(
    max_reviews: Optional[int] = typer.Option(
        None, "--max-reviews", "-n", help="Cap this run at N reviews. 0 = no cap."
    ),
    batch_size: Optional[int] = typer.Option(
        None, "--batch-size", "-b", help="Reviews per LLM call (default from .env)."
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m", help="Override the Groq model id."
    ),
    json_summary: bool = typer.Option(
        False, "--json", help="Print the run summary as JSON instead of a table."
    ),
) -> None:
    """Run the Phase 2 AI analysis pipeline against `data/raw/`."""

    try:
        client = GroqClient(model=model) if model else GroqClient()
    except GroqClientError as exc:
        console.print(f"[red]Groq client error:[/red] {exc}")
        raise typer.Exit(2)

    pipeline = AnalysisPipeline(client=client, max_reviews=max_reviews)
    if batch_size:
        pipeline.analyzer = Analyzer(client=client, batch_size=batch_size)

    summary = pipeline.run()
    payload = AnalysisPipeline.summary_to_dict(summary)

    if json_summary:
        console.print_json(json.dumps(payload, default=str))
        return

    table = Table(title="Phase 2 — AI Analysis Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")

    table.add_row("Reviews considered", str(payload["reviews_considered"]))
    table.add_row("Already analyzed (skipped)", str(payload["reviews_already_analyzed"]))
    table.add_row("Sent to LLM this run", str(payload["reviews_sent_to_llm"]))
    table.add_row("Insights written", f"[green]{payload['insights_written']}[/green]")
    table.add_row("Model", payload["model_used"])
    table.add_row("Duration (sec)", f"{payload['duration_seconds']:.1f}")
    table.add_row("CSV path", payload["csv_path"])

    console.print(table)


if __name__ == "__main__":
    app()
