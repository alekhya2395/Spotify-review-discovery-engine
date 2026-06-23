"""Aggregate insights into ranked pain themes with evidence."""

from __future__ import annotations

from typing import Any

import pandas as pd
from loguru import logger


def build_theme_report(df: pd.DataFrame, top_n: int = 15, quotes_per_theme: int = 5) -> list[dict[str, Any]]:
    """Group by pain_category and produce ranked theme cards."""
    pain_df = df[df["pain_category"] != "none"].copy()
    logger.info("Building themes from {} pain-tagged insights", len(pain_df))

    themes: list[dict[str, Any]] = []
    grouped = pain_df.groupby("pain_category", sort=False)

    for cat, group in grouped:
        neg_count = (group["sentiment"] == "negative").sum()
        total = len(group)
        severity = round(neg_count / total, 2) if total else 0

        top_unmet = (
            group[group["unmet_need"].str.lower() != "none"]["unmet_need"]
            .value_counts()
            .head(5)
            .to_dict()
        )

        quotes = (
            group[group["verbatim_quote"].str.len() > 20]["verbatim_quote"]
            .drop_duplicates()
            .head(quotes_per_theme)
            .tolist()
        )

        segments_hit = group["segment"].value_counts().to_dict()
        sources = group["source"].value_counts().to_dict()

        discovery_pct = round(group["discovery_related"].mean() * 100, 1)

        themes.append({
            "pain_category": cat,
            "review_count": total,
            "negative_ratio": severity,
            "discovery_overlap_pct": discovery_pct,
            "top_unmet_needs": top_unmet,
            "evidence_quotes": quotes,
            "segments_affected": segments_hit,
            "sources": sources,
        })

    themes.sort(key=lambda t: t["review_count"], reverse=True)
    themes = themes[:top_n]

    for rank, theme in enumerate(themes, 1):
        theme["rank"] = rank

    logger.info("Produced {} ranked themes", len(themes))
    return themes


def build_discovery_deep_dive(df: pd.DataFrame) -> dict:
    """Focused analysis on discovery-related reviews only."""
    disc = df[df["discovery_related"] == True].copy()
    total_disc = len(disc)
    logger.info("Discovery deep-dive on {} reviews", total_disc)

    pain_dist = disc["pain_category"].value_counts().to_dict()
    sentiment_dist = disc["sentiment"].value_counts().to_dict()
    segment_dist = disc["segment"].value_counts().to_dict()
    source_dist = disc["source"].value_counts().to_dict()

    top_needs = (
        disc[disc["unmet_need"].str.lower() != "none"]["unmet_need"]
        .value_counts()
        .head(15)
        .to_dict()
    )

    quotes = (
        disc[disc["verbatim_quote"].str.len() > 30]["verbatim_quote"]
        .drop_duplicates()
        .head(20)
        .tolist()
    )

    return {
        "total_discovery_reviews": total_disc,
        "pct_of_all_reviews": round(total_disc / len(df) * 100, 1) if len(df) else 0,
        "pain_distribution": pain_dist,
        "sentiment_distribution": sentiment_dist,
        "segment_distribution": segment_dist,
        "source_distribution": source_dist,
        "top_unmet_needs": top_needs,
        "evidence_quotes": quotes,
    }
