"""Data access layer for the dashboard — wraps QueryEngine with analytics SQL."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from src.phase3_clustering.storage import LIST_DELIM
from src.phase5_storage import QueryEngine

from .config import settings


def _split_list(val) -> list:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return []
    s = str(val).strip()
    if not s:
        return []
    return [x.strip() for x in s.split(LIST_DELIM) if x.strip()]


def _parse_card_row(row: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(row)
    for col in (
        "affected_segments",
        "top_unmet_needs",
        "evidence_quotes",
        "evidence_review_ids",
        "top_sources",
    ):
        if col in out:
            out[col] = _split_list(out[col])
    return out


class DashboardData:
    """Read-only analytics over the Phase-5 index."""

    def __init__(self, engine: Optional[QueryEngine] = None) -> None:
        self.engine = engine or QueryEngine()

    def stats(self) -> Dict[str, Any]:
        return self.engine.stats()

    def all_cards(self, limit: Optional[int] = None) -> pd.DataFrame:
        limit = limit or settings.default_card_limit
        return self.engine.list_cards(limit=limit)

    def card(self, insight_id: str) -> Optional[Dict[str, Any]]:
        row = self.engine.get_card(insight_id)
        return _parse_card_row(row) if row else None

    def topics(self) -> pd.DataFrame:
        return self.engine.warehouse.fetchdf(
            """
            SELECT topic_id, label, size, share_pct, discovery_share_pct,
                   top_pain_category, top_sentiment, top_segment
            FROM topics
            WHERE topic_id >= 0
            ORDER BY size DESC
            """
        )

    def severity_distribution(self) -> pd.DataFrame:
        return self.engine.warehouse.fetchdf(
            """
            SELECT severity, COUNT(*) AS count
            FROM insight_cards
            GROUP BY severity
            ORDER BY count DESC
            """
        )

    def theme_counts(self, top_n: int = 15) -> pd.DataFrame:
        return self.engine.warehouse.fetchdf(
            """
            SELECT theme, COUNT(*) AS count, AVG(priority_score) AS avg_priority
            FROM insight_cards
            GROUP BY theme
            ORDER BY count DESC
            LIMIT ?
            """,
            [top_n],
        )

    def segment_breakdown(self) -> pd.DataFrame:
        return self.engine.warehouse.fetchdf(
            """
            SELECT
                COALESCE(NULLIF(segment, ''), 'unknown') AS segment,
                COUNT(*) AS reviews,
                SUM(CASE WHEN LOWER(sentiment) = 'negative' THEN 1 ELSE 0 END) AS negative,
                SUM(CASE WHEN LOWER(sentiment) = 'positive' THEN 1 ELSE 0 END) AS positive,
                SUM(CASE WHEN discovery_related THEN 1 ELSE 0 END) AS discovery
            FROM reviews_enriched
            GROUP BY 1
            ORDER BY reviews DESC
            """
        )

    def segment_by_pain(self) -> pd.DataFrame:
        return self.engine.warehouse.fetchdf(
            """
            SELECT
                COALESCE(NULLIF(segment, ''), 'unknown') AS segment,
                COALESCE(NULLIF(pain_category, ''), 'other') AS pain_category,
                COUNT(*) AS reviews
            FROM reviews_enriched
            GROUP BY 1, 2
            HAVING reviews >= 3
            ORDER BY reviews DESC
            """
        )

    def source_breakdown(self) -> pd.DataFrame:
        return self.engine.warehouse.fetchdf(
            """
            SELECT source, sentiment, COUNT(*) AS reviews
            FROM reviews_enriched
            GROUP BY source, sentiment
            ORDER BY reviews DESC
            """
        )

    def topic_trends(self) -> pd.DataFrame:
        """Monthly review volume per topic (where timestamps exist)."""
        return self.engine.warehouse.fetchdf(
            """
            SELECT
                DATE_TRUNC('month', TRY_CAST(created_at AS TIMESTAMP)) AS month,
                topic_label,
                topic_id,
                COUNT(*) AS reviews
            FROM reviews_enriched
            WHERE created_at IS NOT NULL
              AND TRY_CAST(created_at AS TIMESTAMP) IS NOT NULL
              AND topic_id >= 0
            GROUP BY 1, 2, 3
            ORDER BY month, reviews DESC
            """
        )

    def top_trending_topics(self, top_n: int = 8) -> pd.DataFrame:
        return self.engine.warehouse.fetchdf(
            """
            SELECT topic_id, title, severity, trend, priority_score,
                   supporting_review_count, discovery_share_pct
            FROM insight_cards
            WHERE LOWER(trend) = 'increasing'
            ORDER BY priority_score DESC
            LIMIT ?
            """,
            [top_n],
        )

    def filter_options(self) -> Dict[str, List[str]]:
        sources = self.engine.warehouse.fetchdf(
            "SELECT DISTINCT source FROM reviews_enriched WHERE source IS NOT NULL ORDER BY 1"
        )
        sentiments = self.engine.warehouse.fetchdf(
            "SELECT DISTINCT sentiment FROM reviews_enriched WHERE sentiment IS NOT NULL ORDER BY 1"
        )
        segments = self.engine.warehouse.fetchdf(
            "SELECT DISTINCT segment FROM reviews_enriched WHERE segment IS NOT NULL ORDER BY 1"
        )
        return {
            "sources": sources["source"].tolist(),
            "sentiments": sentiments["sentiment"].tolist(),
            "segments": segments["segment"].tolist(),
        }

    def search(
        self,
        query: str,
        k: Optional[int] = None,
        source: Optional[str] = None,
        sentiment: Optional[str] = None,
        topic_id: Optional[int] = None,
        discovery_only: bool = False,
    ) -> List[Dict[str, Any]]:
        return self.engine.semantic_search(
            query=query,
            k=k or settings.default_search_k,
            source=source or None,
            sentiment=sentiment or None,
            topic_id=topic_id,
            discovery_only=discovery_only,
        )

    def filter_reviews(
        self,
        source: Optional[str] = None,
        sentiment: Optional[str] = None,
        segment: Optional[str] = None,
        topic_id: Optional[int] = None,
        discovery_only: bool = False,
        limit: int = 50,
    ) -> pd.DataFrame:
        return self.engine.filter_reviews(
            source=source,
            sentiment=sentiment,
            segment=segment,
            topic_id=topic_id,
            discovery_only=discovery_only,
            limit=limit,
        )

    def close(self) -> None:
        self.engine.close()
