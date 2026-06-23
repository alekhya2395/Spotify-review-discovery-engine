"""Phase 5 CLI — build the queryable index (DuckDB + Chroma + catalog).

Examples:
    python run_phase5.py                    # full index build
    python run_phase5.py --skip-vectors     # DuckDB only (no Chroma)
    python run_phase5.py --json             # machine-readable summary
"""

from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.table import Table

from src.phase5_storage import IndexingPipeline

app = typer.Typer(add_completion=False, help="Phase 5 — Storage & Indexing")
console = Console()


@app.command()
def main(
    skip_vectors: bool = typer.Option(
        False, "--skip-vectors", help="Build DuckDB warehouse only; skip Chroma vector index."
    ),
    json_summary: bool = typer.Option(False, "--json", help="Print summary as JSON."),
) -> None:
    """Index all Phase 1–4 outputs into DuckDB + Chroma + SQLite catalog."""

    pipeline = IndexingPipeline(skip_vectors=skip_vectors)
    summary = pipeline.run()
    payload = IndexingPipeline.summary_to_dict(summary)

    if json_summary:
        console.print_json(json.dumps(payload, default=str))
        return

    table = Table(title="Phase 5 — Indexing Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")

    table.add_row("Raw reviews", str(payload["raw_reviews"]))
    table.add_row("Insights (deduped)", str(payload["insights"]))
    table.add_row("Enriched reviews", str(payload["reviews_enriched"]))
    table.add_row("Topics", str(payload["topics"]))
    table.add_row("Insight cards", str(payload["insight_cards"]))
    table.add_row("Vectors indexed", f"[green]{payload['vectors_indexed']}[/green]")
    table.add_row("Catalog run id", str(payload["catalog_run_id"]))
    table.add_row("Duration (sec)", f"{payload['duration_seconds']:.1f}")
    table.add_row("Warehouse", payload["warehouse_path"])
    table.add_row("Chroma index", payload["chroma_path"])
    table.add_row("Catalog DB", payload["catalog_path"])

    console.print(table)
    console.print("\nTry: [bold]python search_reviews.py \"discover weekly genre filter\"[/bold]")


if __name__ == "__main__":
    app()
