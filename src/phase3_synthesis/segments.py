"""Segment-level analysis: compare pain points across user segments."""

from __future__ import annotations

from typing import Any

import pandas as pd
from loguru import logger


def build_segment_report(df: pd.DataFrame) -> list[dict[str, Any]]:
    """For each known segment, show pain distribution and top needs."""
    known = df[df["segment"] != "unknown"].copy()
    logger.info("Segment analysis on {} segment-tagged insights", len(known))

    segments: list[dict[str, Any]] = []
    for seg, group in known.groupby("segment", sort=False):
        pain_dist = group["pain_category"].value_counts().to_dict()
        sentiment_dist = group["sentiment"].value_counts().to_dict()
        disc_pct = round(group["discovery_related"].mean() * 100, 1)

        top_needs = (
            group[group["unmet_need"].str.lower() != "none"]["unmet_need"]
            .value_counts()
            .head(5)
            .to_dict()
        )

        quotes = (
            group[group["verbatim_quote"].str.len() > 20]["verbatim_quote"]
            .drop_duplicates()
            .head(3)
            .tolist()
        )

        segments.append({
            "segment": seg,
            "review_count": len(group),
            "discovery_pct": disc_pct,
            "pain_distribution": pain_dist,
            "sentiment_distribution": sentiment_dist,
            "top_unmet_needs": top_needs,
            "sample_quotes": quotes,
        })

    segments.sort(key=lambda s: s["review_count"], reverse=True)
    logger.info("Produced segment cards for {} segments", len(segments))
    return segments
