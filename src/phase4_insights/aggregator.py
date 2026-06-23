"""Aggregate per-topic signals from Phase-3 clusters.

Implements the non-LLM parts of Phase 4 from architecture.md:
  - Theme aggregation (cluster stats)
  - Segment comparison
  - Evidence linking
  - Trend detection (when review timestamps are available)
"""

from __future__ import annotations

from collections import Counter
from typing import Dict, List, Optional

import pandas as pd
from loguru import logger

from .config import settings
from .schemas import TopicBundle, Trend


_PAIN_THEME_LABELS = {
    "discovery": "Music Discovery",
    "recommendation_quality": "Recommendation Quality",
    "listening_behavior": "Listening Behavior",
    "audio_quality": "Audio Quality",
    "ui_ux": "UI / UX",
    "pricing": "Pricing & Plans",
    "ads": "Advertising",
    "technical": "Technical Reliability",
    "content_availability": "Content Availability",
    "podcasts": "Podcasts",
    "social": "Social Features",
    "other": "Other",
    "none": "General Feedback",
}


def pain_to_theme(pain_category: str) -> str:
    key = (pain_category or "other").strip().lower()
    return _PAIN_THEME_LABELS.get(key, key.replace("_", " ").title())


def _pct(count: int, total: int) -> float:
    return round(100.0 * count / max(1, total), 2)


def _counter_dict(series: pd.Series) -> dict:
    vals = [str(v).strip() for v in series if str(v).strip() and str(v).lower() != "nan"]
    return dict(Counter(vals).most_common())


def _top_unmet_needs(series: pd.Series, k: int = 8) -> List[str]:
    needs = []
    for v in series:
        s = str(v).strip()
        if not s or s.lower() in {"none", "nan"}:
            continue
        needs.append(s)
    return [n for n, _ in Counter(needs).most_common(k)]


def _detect_trend(
    review_ids: List[str],
    timestamps: Dict[str, pd.Timestamp],
) -> tuple[Trend, str]:
    """Compare first-half vs second-half review volume for this cluster."""
    dates = [timestamps[rid] for rid in review_ids if rid in timestamps]
    if len(dates) < 6:
        return Trend.UNKNOWN, "insufficient dated reviews"

    dates = sorted(dates)
    mid = len(dates) // 2
    first_half = len(dates[:mid])
    second_half = len(dates[mid:])
    if first_half == 0:
        return Trend.INCREASING, f"recent surge ({second_half} dated reviews in later half)"

    ratio = second_half / first_half
    if ratio >= 1.35:
        return Trend.INCREASING, f"later-half volume {ratio:.1f}x first half"
    if ratio <= 0.75:
        return Trend.DECREASING, f"later-half volume {ratio:.1f}x first half"
    return Trend.STABLE, f"balanced volume (ratio={ratio:.2f})"


class ThemeAggregator:
    """Build TopicBundle objects ready for LLM synthesis or rule-based fallback."""

    def __init__(
        self,
        min_topic_size: Optional[int] = None,
        include_noise: Optional[bool] = None,
        discovery_only: Optional[bool] = None,
        min_discovery_share: Optional[float] = None,
        max_evidence: Optional[int] = None,
    ) -> None:
        self.min_topic_size = min_topic_size or settings.min_topic_size
        self.include_noise = (
            include_noise if include_noise is not None else settings.include_noise_topic
        )
        self.discovery_only = (
            discovery_only if discovery_only is not None else settings.discovery_topics_only
        )
        self.min_discovery_share = (
            min_discovery_share if min_discovery_share is not None
            else settings.min_discovery_share_pct
        )
        self.max_evidence = max_evidence or settings.max_evidence_quotes

    def build_bundles(
        self,
        topics_df: pd.DataFrame,
        insights_df: pd.DataFrame,
        timestamps: Optional[Dict[str, pd.Timestamp]] = None,
    ) -> List[TopicBundle]:
        timestamps = timestamps or {}
        bundles: List[TopicBundle] = []

        for _, row in topics_df.iterrows():
            tid = int(row["topic_id"])
            if tid == -1 and not self.include_noise:
                continue
            size = int(row["size"])
            if size < self.min_topic_size:
                continue

            discovery_pct = float(row.get("discovery_share_pct", 0) or 0)
            if self.discovery_only and discovery_pct < self.min_discovery_share:
                continue

            sub = insights_df[insights_df["topic_id"] == tid]
            if sub.empty:
                continue

            quotes: List[str] = []
            rids: List[str] = []
            for q, rid in zip(sub["verbatim_quote"], sub["review_id"]):
                q = str(q).strip()
                rid = str(rid).strip()
                if not q or rid in rids:
                    continue
                quotes.append(q)
                rids.append(rid)
                if len(quotes) >= self.max_evidence:
                    break

            # Pad from topic row if cluster is sparse on quotes
            if len(quotes) < self.max_evidence and isinstance(row.get("representative_quotes"), list):
                for q, rid in zip(row["representative_quotes"], row.get("representative_review_ids", [])):
                    if q and q not in quotes:
                        quotes.append(q)
                        rids.append(str(rid))
                    if len(quotes) >= self.max_evidence:
                        break

            neg_share = _pct(int((sub["sentiment"] == "negative").sum()), len(sub))
            trend, trend_detail = _detect_trend(rids, timestamps)

            bundles.append(
                TopicBundle(
                    topic_id=tid,
                    label=str(row["label"]),
                    size=size,
                    share_pct=float(row.get("share_pct", 0) or 0),
                    discovery_share_pct=discovery_pct,
                    top_pain_category=str(row.get("top_pain_category", "other")),
                    top_sentiment=str(row.get("top_sentiment", "neutral")),
                    top_segment=str(row.get("top_segment", "unknown")),
                    keywords=list(row.get("keywords") or [])[:10],
                    top_sources=list(row.get("top_sources") or [])[:3],
                    sentiment_breakdown=_counter_dict(sub["sentiment"]),
                    segment_breakdown=_counter_dict(sub["segment"]),
                    pain_breakdown=_counter_dict(sub["pain_category"]),
                    source_breakdown=_counter_dict(sub["source"]),
                    unmet_needs=_top_unmet_needs(sub["unmet_need"]),
                    evidence_quotes=quotes,
                    evidence_review_ids=rids[: len(quotes)],
                    negative_share_pct=neg_share,
                    trend=trend,
                    trend_detail=trend_detail,
                )
            )

        bundles.sort(key=lambda b: (-b.size, b.topic_id))
        logger.info("[aggregator] built {n} topic bundles for card generation", n=len(bundles))
        return bundles
