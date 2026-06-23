"""Priority scoring for insight cards.

Ranks clusters by: volume x sentiment severity x discovery relevance x trend.

Architecture: "Rank insights by volume x sentiment severity x recency"
"""

from __future__ import annotations

from typing import List

from .schemas import InsightCard, Severity, TopicBundle, Trend


_TREND_BOOST = {
    Trend.INCREASING: 1.15,
    Trend.STABLE: 1.0,
    Trend.DECREASING: 0.85,
    Trend.UNKNOWN: 0.95,
}


def _severity_from_bundle(bundle: TopicBundle) -> Severity:
    """Heuristic severity before LLM override."""
    if bundle.negative_share_pct >= 55 or (
        bundle.top_sentiment == "negative" and bundle.size >= 25
    ):
        return Severity.HIGH
    if bundle.negative_share_pct >= 30 or bundle.size >= 40:
        return Severity.MEDIUM
    return Severity.LOW


def compute_priority_score(bundle: TopicBundle, max_size: int) -> float:
    """Return a 0-100 priority score."""
    volume = min(1.0, bundle.size / max(1, max_size))

    # Sentiment severity: weight negative/mixed complaints higher
    neg = bundle.negative_share_pct / 100.0
    mixed = bundle.sentiment_breakdown.get("mixed", 0) / max(1, bundle.size)
    sentiment_severity = min(1.0, 0.55 * neg + 0.25 * mixed + 0.2 * (1 if bundle.top_sentiment == "negative" else 0))

    discovery = min(1.0, bundle.discovery_share_pct / 100.0)
    discovery_boost = 0.7 + 0.3 * discovery  # 0.7-1.0

    trend_boost = _TREND_BOOST.get(bundle.trend, 1.0)

    raw = volume * (0.45 + 0.55 * sentiment_severity) * discovery_boost * trend_boost
    return round(min(100.0, raw * 100.0), 2)


def score_bundles(bundles: List[TopicBundle]) -> dict[int, float]:
    if not bundles:
        return {}
    max_size = max(b.size for b in bundles)
    return {b.topic_id: compute_priority_score(b, max_size) for b in bundles}


def default_severity(bundle: TopicBundle) -> Severity:
    return _severity_from_bundle(bundle)
