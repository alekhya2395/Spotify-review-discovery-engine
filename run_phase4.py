"""Phase 4 CLI — PM-ready insight card generation.

Examples:
    python run_phase4.py                          # Groq RAG cards from Phase 3 topics
    python run_phase4.py --no-llm                   # rule-based cards only (offline)
    python run_phase4.py --discovery-only           # only discovery-heavy clusters
    python run_phase4.py --min-topic-size 15        # skip small clusters
    python run_phase4.py -m openai/gpt-oss-20b      # override Groq model
    python run_phase4.py --json                     # machine-readable summary
"""

from __future__ import annotations

import json
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from src.phase4_insights import GenerationPipeline
from src.phase4_insights.aggregator import ThemeAggregator
from src.phase4_insights.generator import CardGenerator

app = typer.Typer(add_completion=False, help="Phase 4 — Insight Generation (PM-ready cards)")
console = Console()


@app.command()
def main(
    min_topic_size: Optional[int] = typer.Option(
        None, "--min-topic-size",
        help="Skip clusters with fewer than N reviews (default from .env).",
    ),
    discovery_only: bool = typer.Option(
        False, "--discovery-only/--all",
        help="Only synthesize cards for discovery-heavy clusters.",
    ),
    include_noise: bool = typer.Option(
        False, "--include-noise",
        help="Include the BERTopic noise bucket (topic_id=-1).",
    ),
    no_llm: bool = typer.Option(
        False, "--no-llm",
        help="Skip Groq; emit rule-based cards from aggregated stats only.",
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m", help="Override the Groq model id."
    ),
    json_summary: bool = typer.Option(
        False, "--json", help="Print summary as JSON."
    ),
) -> None:
    """Generate PM-ready insight cards from Phase 3 topic clusters."""

    aggregator = ThemeAggregator(
        min_topic_size=min_topic_size,
        include_noise=include_noise,
        discovery_only=discovery_only if discovery_only else None,
    )
    generator = CardGenerator(use_llm=not no_llm, model=model)

    pipeline = GenerationPipeline(
        aggregator=aggregator,
        generator=generator,
        use_llm=not no_llm,
        model=model,
    )
    summary = pipeline.run()
    payload = GenerationPipeline.summary_to_dict(summary)

    if json_summary:
        console.print_json(json.dumps(payload, default=str))
        return

    table = Table(title="Phase 4 — Insight Generation Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")

    table.add_row("Topics on disk", str(payload["topics_on_disk"]))
    table.add_row("Bundles synthesized", str(payload["bundles_built"]))
    table.add_row("Insight cards written", f"[green]{payload['cards_generated']}[/green]")
    table.add_row("LLM-generated cards", str(payload["llm_cards"]))
    table.add_row("Rule-based cards", str(payload["rule_based_cards"]))
    table.add_row("Model", payload["model_used"])
    table.add_row("Top priority card", payload["top_insight_id"])
    table.add_row("Top priority score", f"{payload['top_priority_score']:.1f}")
    table.add_row("Duration (sec)", f"{payload['duration_seconds']:.1f}")
    table.add_row("CSV path", payload["csv_path"])
    table.add_row("JSON path", payload["json_path"])

    console.print(table)


if __name__ == "__main__":
    app()
