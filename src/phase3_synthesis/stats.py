"""Compute high-level summary statistics for the dashboard."""

from __future__ import annotations

from typing import Any

import pandas as pd
from loguru import logger


def compute_summary_stats(df: pd.DataFrame) -> dict[str, Any]:
    """Produce top-level numbers for the overview page."""
    total = len(df)
    discovery_count = int(df["discovery_related"].sum())
    sources = df["source"].nunique()

    pain_counts = df[df["pain_category"] != "none"]["pain_category"].value_counts()
    top_pain = pain_counts.index[0] if len(pain_counts) > 0 else "none"
    unique_pains = len(pain_counts)

    sentiment_dist = df["sentiment"].value_counts().to_dict()
    segment_dist = df["segment"].value_counts().to_dict()
    source_dist = df["source"].value_counts().to_dict()
    pain_dist = df["pain_category"].value_counts().to_dict()

    avg_confidence = round(df["confidence"].mean(), 2) if df["confidence"].notna().any() else 0

    logger.info(
        "Summary: {} total, {} discovery, {} sources, top pain={}",
        total, discovery_count, sources, top_pain,
    )

    return {
        "total_reviews_analyzed": total,
        "discovery_related_count": discovery_count,
        "discovery_related_pct": round(discovery_count / total * 100, 1) if total else 0,
        "data_sources_count": sources,
        "unique_pain_categories": unique_pains,
        "top_pain_category": top_pain,
        "avg_confidence": avg_confidence,
        "sentiment_distribution": sentiment_dist,
        "segment_distribution": segment_dist,
        "source_distribution": source_dist,
        "pain_category_distribution": pain_dist,
    }
