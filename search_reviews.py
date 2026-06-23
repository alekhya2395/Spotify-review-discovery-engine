"""Query the Phase-5 index — semantic search, filters, and insight cards.

Examples:
    python search_reviews.py "workout playlist discovery"
    python search_reviews.py --filter --source reddit --sentiment negative
    python search_reviews.py --cards --severity high
    python search_reviews.py --card INS-026
    python search_reviews.py --stats
"""

from __future__ import annotations

import sys
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from src.phase5_storage import QueryEngine


try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


app = typer.Typer(add_completion=False, help="Query the Phase 5 index.")
console = Console()


@app.command()
def main(
    query: Optional[str] = typer.Argument(None, help="Natural-language semantic search query."),
    k: int = typer.Option(10, "--top", "-n", help="Number of semantic search results."),
    source: Optional[str] = typer.Option(None, "--source", "-s"),
    sentiment: Optional[str] = typer.Option(None, "--sentiment"),
    topic_id: Optional[int] = typer.Option(None, "--topic", "-t"),
    discovery_only: bool = typer.Option(False, "--discovery-only"),
    filter_mode: bool = typer.Option(False, "--filter", "-f", help="Structured filter instead of semantic search."),
    cards: bool = typer.Option(False, "--cards", help="List insight cards by priority."),
    severity: Optional[str] = typer.Option(None, "--severity", help="Filter cards: high/medium/low."),
    theme: Optional[str] = typer.Option(None, "--theme"),
    min_priority: Optional[float] = typer.Option(None, "--min-priority"),
    card: Optional[str] = typer.Option(None, "--card", "-c", help="Show one insight card in full."),
    stats: bool = typer.Option(False, "--stats", help="Show index statistics."),
) -> None:
    engine = QueryEngine()
    try:
        if stats:
            s = engine.stats()
            table = Table(title="Index Statistics")
            table.add_column("Store", style="cyan")
            table.add_column("Count", justify="right")
            for key, val in s.items():
                table.add_row(key, str(val))
            console.print(table)
            return

        if card:
            row = engine.get_card(card)
            if not row:
                console.print(f"[red]No card {card}[/red]")
                raise typer.Exit(1)
            console.print(f"\n[bold green]{row['insight_id']}[/bold green]  priority={row['priority_score']}")
            console.print(f"[bold]{row['title']}[/bold]")
            console.print(f"  theme: {row['theme']}  severity: {row['severity']}  trend: {row['trend']}")
            console.print(f"\n  {row['narrative']}")
            console.print(f"\n  Opportunity: {row['suggested_opportunity']}")
            return

        if cards:
            df = engine.list_cards(severity=severity, theme=theme, min_priority=min_priority, limit=k)
            table = Table(title="Insight Cards")
            table.add_column("ID")
            table.add_column("Pri", justify="right")
            table.add_column("Sev")
            table.add_column("Title")
            for _, r in df.iterrows():
                table.add_row(
                    str(r["insight_id"]),
                    f"{r['priority_score']:.1f}",
                    str(r["severity"]),
                    str(r["title"])[:60],
                )
            console.print(table)
            return

        if filter_mode or (query is None and not cards):
            df = engine.filter_reviews(
                source=source,
                sentiment=sentiment,
                topic_id=topic_id,
                discovery_only=discovery_only,
                limit=k,
            )
            table = Table(title=f"Filtered Reviews (n={len(df)})")
            table.add_column("review_id")
            table.add_column("source")
            table.add_column("sentiment")
            table.add_column("topic")
            table.add_column("quote")
            for _, r in df.iterrows():
                table.add_row(
                    str(r["review_id"])[:40],
                    str(r.get("source", "")),
                    str(r.get("sentiment", "")),
                    str(r.get("topic_label", ""))[:30],
                    str(r.get("verbatim_quote", ""))[:80],
                )
            console.print(table)
            return

        if not query:
            console.print("[yellow]Provide a search query or use --filter / --cards / --stats[/yellow]")
            raise typer.Exit(1)

        hits = engine.semantic_search(
            query=query,
            k=k,
            source=source,
            sentiment=sentiment,
            topic_id=topic_id,
            discovery_only=discovery_only,
        )
        table = Table(title=f'Semantic search: "{query}"')
        table.add_column("#", justify="right")
        table.add_column("Sim", justify="right")
        table.add_column("Source")
        table.add_column("Sentiment")
        table.add_column("Topic")
        table.add_column("Quote")

        for i, hit in enumerate(hits, start=1):
            detail = hit.get("detail") or hit.get("metadata") or {}
            sim = hit.get("similarity")
            table.add_row(
                str(i),
                f"{sim:.3f}" if sim is not None else "",
                str(detail.get("source", "")),
                str(detail.get("sentiment", "")),
                str(detail.get("topic_label", ""))[:28],
                str(detail.get("verbatim_quote") or hit.get("document", ""))[:90],
            )
        console.print(table)
    finally:
        engine.close()


if __name__ == "__main__":
    app()
