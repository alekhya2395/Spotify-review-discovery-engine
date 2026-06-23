"""Generate the final synthesis report as JSON + Markdown."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger


def _fmt_dict(d: dict, indent: int = 0) -> str:
    """Format a dict as a markdown list."""
    prefix = "  " * indent
    lines = []
    for k, v in d.items():
        lines.append(f"{prefix}- **{k}**: {v}")
    return "\n".join(lines)


def generate_report(
    stats: dict[str, Any],
    themes: list[dict[str, Any]],
    segments: list[dict[str, Any]],
    discovery: dict[str, Any],
    output_dir: Path,
) -> tuple[Path, Path]:
    """Write synthesis_report.json and synthesis_report.md."""
    output_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": stats,
        "pain_themes": themes,
        "segment_analysis": segments,
        "discovery_deep_dive": discovery,
    }

    json_path = output_dir / "synthesis_report.json"
    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    logger.info("Wrote JSON report → {}", json_path)

    md = _build_markdown(stats, themes, segments, discovery)
    md_path = output_dir / "synthesis_report.md"
    md_path.write_text(md, encoding="utf-8")
    logger.info("Wrote Markdown report → {}", md_path)

    return json_path, md_path


def _build_markdown(
    stats: dict, themes: list[dict], segments: list[dict], discovery: dict
) -> str:
    lines = [
        "# Spotify Review Discovery Engine — Synthesis Report",
        "",
        f"*Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*",
        "",
        "---",
        "",
        "## Executive Summary",
        "",
        f"- **Total reviews analyzed:** {stats['total_reviews_analyzed']:,}",
        f"- **Discovery-related:** {stats['discovery_related_count']:,} ({stats['discovery_related_pct']}%)",
        f"- **Data sources:** {stats['data_sources_count']}",
        f"- **Top pain category:** {stats['top_pain_category']}",
        f"- **Avg LLM confidence:** {stats['avg_confidence']}",
        "",
        "### Sentiment Distribution",
        "",
        _fmt_dict(stats["sentiment_distribution"]),
        "",
        "### Source Distribution",
        "",
        _fmt_dict(stats["source_distribution"]),
        "",
        "---",
        "",
        "## Top Pain Themes",
        "",
    ]

    for t in themes:
        lines.append(f"### {t['rank']}. {t['pain_category'].replace('_', ' ').title()}")
        lines.append("")
        lines.append(f"- **Reviews:** {t['review_count']} | **Negative ratio:** {t['negative_ratio']} | **Discovery overlap:** {t['discovery_overlap_pct']}%")
        lines.append("")
        if t["top_unmet_needs"]:
            lines.append("**Top unmet needs:**")
            lines.append("")
            for need, count in t["top_unmet_needs"].items():
                lines.append(f"  - {need} ({count})")
            lines.append("")
        if t["evidence_quotes"]:
            lines.append("**Evidence quotes:**")
            lines.append("")
            for q in t["evidence_quotes"]:
                lines.append(f'  > "{q}"')
            lines.append("")
        lines.append("")

    lines.extend([
        "---",
        "",
        "## Discovery Deep Dive",
        "",
        f"- **Total discovery-related reviews:** {discovery['total_discovery_reviews']:,} ({discovery['pct_of_all_reviews']}% of all)",
        "",
        "### Pain Distribution (discovery only)",
        "",
        _fmt_dict(discovery["pain_distribution"]),
        "",
        "### Top Unmet Needs (discovery only)",
        "",
    ])
    for need, count in discovery["top_unmet_needs"].items():
        lines.append(f"- {need} ({count})")
    lines.append("")

    if discovery["evidence_quotes"]:
        lines.append("### Key Quotes")
        lines.append("")
        for q in discovery["evidence_quotes"][:10]:
            lines.append(f'> "{q}"')
            lines.append("")

    lines.extend([
        "---",
        "",
        "## Segment Analysis",
        "",
    ])
    for s in segments:
        lines.append(f"### {s['segment'].replace('_', ' ').title()} ({s['review_count']} reviews)")
        lines.append("")
        lines.append(f"- **Discovery %:** {s['discovery_pct']}%")
        lines.append("")
        lines.append("**Pain distribution:**")
        lines.append("")
        lines.append(_fmt_dict(s["pain_distribution"], indent=1))
        lines.append("")
        if s["top_unmet_needs"]:
            lines.append("**Top needs:**")
            lines.append("")
            for need, count in s["top_unmet_needs"].items():
                lines.append(f"  - {need} ({count})")
            lines.append("")
        lines.append("")

    return "\n".join(lines)
