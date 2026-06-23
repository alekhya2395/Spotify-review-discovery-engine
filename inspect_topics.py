"""Pretty-print the topics produced by Phase 3.

Usage:
    python inspect_topics.py           # show top 20 topics
    python inspect_topics.py --top 50  # show top 50
    python inspect_topics.py --topic 7 # show one topic in detail (all quotes)
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import pandas as pd
import typer
from rich.console import Console
from rich.table import Table

from src.phase3_clustering.config import settings
from src.phase3_clustering.storage import LIST_DELIM


# Force UTF-8 stdout so non-ASCII characters in user reviews (Unicode hyphens,
# accented chars, etc.) don't crash on Windows' default cp1252 console.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


app = typer.Typer(add_completion=False, help="Inspect topics.csv produced by Phase 3.")
console = Console()


def _split_list(s) -> list:
    if pd.isna(s) or not str(s).strip():
        return []
    return [x.strip() for x in str(s).split(LIST_DELIM) if x.strip()]


def _read_topics(path: Path) -> pd.DataFrame:
    if not path.exists():
        console.print(f"[red]topics.csv not found at {path}. Run `python run_phase3.py` first.[/red]")
        raise typer.Exit(1)
    df = pd.read_csv(path)
    for col in ("keywords", "representative_quotes", "representative_review_ids", "top_sources"):
        if col in df.columns:
            df[col] = df[col].map(_split_list)
    return df


@app.command()
def main(
    top: int = typer.Option(20, "--top", "-n", help="Show this many topics in the overview."),
    topic: Optional[int] = typer.Option(
        None, "--topic", "-t", help="Show one topic in detail (full quotes)."
    ),
) -> None:
    path = settings.topics_csv_path
    df = _read_topics(path)

    if topic is not None:
        row = df[df["topic_id"] == topic]
        if row.empty:
            console.print(f"[red]No topic with id={topic}[/red]")
            raise typer.Exit(1)
        r = row.iloc[0]
        console.print(f"\n[bold green]Topic {r['topic_id']}[/bold green]  —  [bold]{r['label']}[/bold]")
        console.print(f"  size:       {int(r['size'])}  ({r['share_pct']}% of clustered)")
        console.print(f"  discovery:  {r['discovery_share_pct']}% discovery-related")
        console.print(f"  pain:       {r['top_pain_category']}")
        console.print(f"  sentiment:  {r['top_sentiment']}")
        console.print(f"  segment:    {r['top_segment']}")
        console.print(f"  sources:    {', '.join(r['top_sources'])}")
        console.print(f"  keywords:   {', '.join(r['keywords'][:10])}")
        console.print("\n  [bold]Representative quotes:[/bold]")
        for q in r["representative_quotes"]:
            console.print(f"   - {q}")
        return

    # Overview table
    table = Table(title=f"Top {top} topics from {path}", show_lines=False)
    table.add_column("ID", justify="right")
    table.add_column("Size", justify="right", style="green")
    table.add_column("%", justify="right")
    table.add_column("Disc%", justify="right")
    table.add_column("Pain", style="magenta")
    table.add_column("Sent", style="yellow")
    table.add_column("Label", style="bold")
    table.add_column("Keywords")

    df_show = df.copy()
    # show noise row last, real topics ranked by size
    df_show = pd.concat([
        df_show[df_show["topic_id"] != -1].sort_values("size", ascending=False).head(top),
        df_show[df_show["topic_id"] == -1],
    ])

    for _, r in df_show.iterrows():
        kw = ", ".join(r["keywords"][:6])
        table.add_row(
            str(int(r["topic_id"])),
            str(int(r["size"])),
            f"{r['share_pct']:.1f}",
            f"{r['discovery_share_pct']:.0f}",
            str(r["top_pain_category"]),
            str(r["top_sentiment"]),
            str(r["label"])[:55],
            kw[:80],
        )

    console.print(table)
    console.print(
        f"\nTotal topics: [bold]{int((df['topic_id'] >= 0).sum())}[/bold]  "
        f"| Noise reviews: {int(df.loc[df['topic_id'] == -1, 'size'].sum()) if (-1 in df['topic_id'].values) else 0}"
        f"\nFor full quotes:  python inspect_topics.py --topic <ID>"
    )


if __name__ == "__main__":
    app()
