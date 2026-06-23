"""Export PM-ready insight digests (Markdown + JSON)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from src.phase3_clustering.storage import LIST_DELIM

from .config import settings
from .data import DashboardData, _parse_card_row


def _cards_to_records(cards: pd.DataFrame) -> list[dict]:
    records = []
    for _, row in cards.iterrows():
        records.append(_parse_card_row(row.to_dict()))
    return records


def build_markdown_digest(
    data: DashboardData,
    top_n: int = 15,
    include_evidence: bool = True,
) -> str:
    stats = data.stats()
    cards = data.all_cards(limit=top_n)
    lines = [
        "# Spotify Review Discovery — Weekly Insight Digest",
        "",
        f"_Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_",
        "",
        "## Corpus snapshot",
        "",
        f"- Raw reviews: **{stats.get('raw_reviews', 0):,}**",
        f"- Enriched reviews: **{stats.get('reviews_enriched', 0):,}**",
        f"- Insight cards: **{stats.get('insight_cards', 0):,}**",
        f"- Topic clusters: **{stats.get('topics', 0):,}**",
        "",
        "## Top priority insights",
        "",
    ]

    for i, row in cards.iterrows():
        card = data.card(str(row["insight_id"]))
        if not card:
            continue
        lines.extend(
            [
                f"### {card['insight_id']} — {card['title']}",
                "",
                f"- **Priority:** {card['priority_score']:.1f} | **Severity:** {card['severity']} | **Trend:** {card['trend']}",
                f"- **Reviews:** {card['supporting_review_count']} | **Discovery share:** {card['discovery_share_pct']:.0f}%",
                f"- **Theme:** {card['theme']}",
                "",
                card["narrative"],
                "",
                f"**Suggested opportunity:** {card['suggested_opportunity']}",
                "",
            ]
        )
        if include_evidence and card.get("evidence_quotes"):
            lines.append("**Evidence:**")
            for q in card["evidence_quotes"][:5]:
                lines.append(f"- \"{q}\"")
            lines.append("")

    lines.append("---")
    lines.append("*Exported from Phase 6 Review Discovery Dashboard*")
    return "\n".join(lines)


def export_digest(
    data: DashboardData,
    top_n: int = 15,
    output_dir: Optional[Path] = None,
) -> dict[str, Path]:
    """Write Markdown + JSON digest files. Returns paths written."""
    out_dir = output_dir or settings.export_dir_path
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")

    cards = data.all_cards(limit=top_n)
    md_path = out_dir / f"insight_digest_{stamp}.md"
    json_path = out_dir / f"insight_digest_{stamp}.json"

    md_path.write_text(build_markdown_digest(data, top_n=top_n), encoding="utf-8")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stats": data.stats(),
        "cards": _cards_to_records(cards),
    }
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    return {"markdown": md_path, "json": json_path}
