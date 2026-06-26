"""Confidence scoring for review-backed insights.

Confidence reflects three signals:
  1. Number of supporting reviews
  2. Frequency within the relevant pool / corpus
  3. Consistency across review sources (App Store, Play Store, Reddit, etc.)
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

_SOURCE_LABELS: dict[str, str] = {
    "app_store": "App Store",
    "play_store": "Play Store",
    "reddit": "Reddit",
    "social_media": "Social Media",
    "community_forum": "Community Forums",
}

# Minimum reviews in a source before it counts toward cross-source consistency.
_MIN_SOURCE_REVIEWS = 3


def format_source_label(source: str | None) -> str | None:
    if not source:
        return None
    key = str(source).strip().lower()
    if not key:
        return None
    return _SOURCE_LABELS.get(key, str(source).replace("_", " ").title())


def source_counts_from_frame(df: pd.DataFrame) -> dict[str, int]:
    """Return ``{display_label: count}`` for a slice of reviews."""
    if df.empty or "source" not in df.columns:
        return {}
    series = df["source"].astype(str).str.strip().str.lower()
    series = series[series.ne("") & ~series.isin({"none", "nan", "null"})]
    if series.empty:
        return {}
    out: dict[str, int] = {}
    for raw, count in series.value_counts().items():
        label = format_source_label(raw) or raw
        out[label] = out.get(label, 0) + int(count)
    return out


def parse_share_percent(share: str | float | None) -> float | None:
    if share is None:
        return None
    if isinstance(share, (int, float)):
        return float(share)
    text = str(share).strip()
    if not text:
        return None
    match = re.search(r"([\d.]+)\s*%", text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _active_source_count(source_counts: dict[str, int]) -> int:
    return sum(1 for c in source_counts.values() if c >= _MIN_SOURCE_REVIEWS)


def compute_confidence(
    count: int,
    *,
    share: str | float | None = None,
    source_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Score an insight and build a human-readable support line."""
    source_counts = source_counts or {}
    share_pct = parse_share_percent(share)
    active_sources = _active_source_count(source_counts)

    level = "Low"
    if count >= 80 and active_sources >= 2:
        level = "High"
    elif count >= 50 and (active_sources >= 2 or (share_pct is not None and share_pct >= 5.0)):
        level = "High"
    elif count >= 25 and active_sources >= 2:
        level = "Medium"
    elif count >= 15 and (
        active_sources >= 2 or (share_pct is not None and share_pct >= 2.0)
    ):
        level = "Medium"
    elif count >= 10:
        level = "Low"

    support_line = format_support_line(count, source_counts)
    return {
        "level": level,
        "support_line": support_line,
        "source_counts": source_counts,
        "active_sources": active_sources,
    }


def format_support_line(count: int, source_counts: dict[str, int]) -> str:
    """e.g. ``119 reviews across App Store, Play Store and Reddit``."""
    review_word = "review" if count == 1 else "reviews"
    ranked = sorted(source_counts.items(), key=lambda kv: -kv[1])
    significant = [name for name, n in ranked if n >= _MIN_SOURCE_REVIEWS]
    if not significant:
        return f"{count:,} {review_word} in the analyzed corpus"
    if len(significant) == 1:
        return f"{count:,} {review_word} from {significant[0]}"
    if len(significant) == 2:
        return f"{count:,} {review_word} across {significant[0]} and {significant[1]}"
    head = ", ".join(significant[:-1])
    return f"{count:,} {review_word} across {head} and {significant[-1]}"


def enrich_finding(
    finding: dict[str, Any],
    *,
    count: int | None = None,
    share: str | float | None = None,
    source_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Attach ``confidence`` fields to a finding dict (mutates and returns)."""
    n = int(count if count is not None else finding.get("count") or 0)
    share_val = share if share is not None else finding.get("share") or finding.get("share_of_corpus") or finding.get("share_of_pool")
    sources = source_counts if source_counts is not None else finding.get("source_counts") or {}
    conf = compute_confidence(n, share=share_val, source_counts=sources)
    finding["source_counts"] = sources
    finding["confidence"] = conf["level"]
    finding["confidence_support"] = conf["support_line"]
    return finding


def confidence_markdown_lines(level: str, support_line: str) -> list[str]:
    return [
        f"  - **Confidence:** {level}",
        f"  - **Supported by:** {support_line}",
    ]


def source_counts_for_pain_category(pain_key: str, df: pd.DataFrame | None = None) -> dict[str, int]:
    if df is None:
        from data_loader import load_insights_df

        df = load_insights_df()
    if df.empty or "pain_category" not in df.columns:
        return {}
    key = str(pain_key or "").strip().lower()
    if not key:
        return {}
    mask = df["pain_category"].astype(str).str.lower().str.strip() == key
    return source_counts_from_frame(df[mask])


__all__ = [
    "compute_confidence",
    "confidence_markdown_lines",
    "enrich_finding",
    "format_source_label",
    "format_support_line",
    "parse_share_percent",
    "source_counts_for_pain_category",
    "source_counts_from_frame",
]
