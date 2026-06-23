"""Pretty-print PM-ready insight cards from Phase 4.

Usage:
    python inspect_cards.py              # top 15 by priority
    python inspect_cards.py --top 30
    python inspect_cards.py --card INS-007
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import pandas as pd
import typer
from rich.console import Console
from rich.table import Table

from src.phase3_clustering.storage import LIST_DELIM
from src.phase4_insights.config import settings


try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


app = typer.Typer(add_completion=False, help="Inspect insight_cards.csv from Phase 4.")
console = Console()


def _split_list(val) -> list:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return []
    s = str(val).strip()
    if not s:
        return []
    return [x.strip() for x in s.split(LIST_DELIM) if x.strip()]


def _load_cards(path: Path) -> pd.DataFrame:
    if not path.exists():
        console.print(f"[red]insight_cards.csv not found at {path}. Run `python run_phase4.py` first.[/red]")
        raise typer.Exit(1)
    df = pd.read_csv(path)
    for col in ("affected_segments", "top_unmet_needs", "evidence_quotes", "evidence_review_ids", "top_sources"):
        if col in df.columns:
            df[col] = df[col].map(_split_list)
    return df.sort_values("priority_score", ascending=False).reset_index(drop=True)


@app.command()
def main(
    top: int = typer.Option(15, "--top", "-n", help="Show this many cards in the overview."),
    card: Optional[str] = typer.Option(None, "--card", "-c", help="Show one card in full detail."),
) -> None:
    path = settings.insight_cards_csv_path
    df = _load_cards(path)

    if card is not None:
        row = df[df["insight_id"] == card]
        if row.empty:
            console.print(f"[red]No card with id={card}[/red]")
            raise typer.Exit(1)
        r = row.iloc[0]
        console.print(f"\n[bold green]{r['insight_id']}[/bold green]  priority={r['priority_score']:.1f}  severity={r['severity']}")
        console.print(f"[bold]{r['title']}[/bold]")
        console.print(f"  theme:      {r['theme']}")
        console.print(f"  topic_id:   {int(r['topic_id'])}")
        console.print(f"  reviews:    {int(r['supporting_review_count'])}  |  discovery: {r['discovery_share_pct']}%  |  negative: {r['negative_share_pct']}%")
        console.print(f"  trend:      {r['trend']}")
        console.print(f"  segments:   {', '.join(r['affected_segments'])}")
        console.print(f"  sources:    {', '.join(r['top_sources'])}")
        console.print(f"  model:      {r['model_used']}")
        console.print(f"\n  [bold]Narrative:[/bold]\n  {r['narrative']}")
        console.print(f"\n  [bold]Suggested opportunity:[/bold]\n  {r['suggested_opportunity']}")
        if r.get("segment_notes") and str(r["segment_notes"]).strip() not in ("", "nan"):
            console.print(f"\n  [bold]Segment notes:[/bold]\n  {r['segment_notes']}")
        console.print("\n  [bold]Unmet needs:[/bold]")
        for n in r["top_unmet_needs"]:
            console.print(f"   - {n}")
        console.print("\n  [bold]Evidence quotes:[/bold]")
        for q in r["evidence_quotes"]:
            console.print(f"   - {q}")
        return

    table = Table(title=f"Top {top} insight cards by priority ({path})", show_lines=False)
    table.add_column("ID", style="cyan")
    table.add_column("Pri", justify="right", style="green")
    table.add_column("Sev")
    table.add_column("Trend")
    table.add_column("Reviews", justify="right")
    table.add_column("Disc%", justify="right")
    table.add_column("Title", style="bold")
    table.add_column("Theme")

    for _, r in df.head(top).iterrows():
        table.add_row(
            str(r["insight_id"]),
            f"{r['priority_score']:.1f}",
            str(r["severity"]),
            str(r["trend"]),
            str(int(r["supporting_review_count"])),
            f"{r['discovery_share_pct']:.0f}",
            str(r["title"])[:55],
            str(r["theme"])[:28],
        )

    console.print(table)
    console.print(
        f"\nTotal cards: [bold]{len(df)}[/bold]"
        f"\nFull detail:  python inspect_cards.py --card INS-007"
    )


if __name__ == "__main__":
    app()
