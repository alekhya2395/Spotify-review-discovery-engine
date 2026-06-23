"""Query engine — semantic search, filters, and insight card lookups."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd
from loguru import logger

from .config import settings
from .vector_index import VectorIndex
from .warehouse import DuckDBWarehouse


class QueryEngine:
    """Unified read API over the DuckDB warehouse + Chroma vector index."""

    def __init__(
        self,
        warehouse: Optional[DuckDBWarehouse] = None,
        vector_index: Optional[VectorIndex] = None,
    ) -> None:
        wh_path = settings.warehouse_path
        if not wh_path.exists():
            raise FileNotFoundError(
                f"Warehouse not found at {wh_path}. Run `python run_phase5.py` first."
            )
        self.warehouse = warehouse or DuckDBWarehouse(wh_path)
        self.vector = vector_index or VectorIndex()
        self._embedder = None

    def _embed_query(self, query: str) -> List[float]:
        if self._embedder is None:
            from src.phase3_clustering.embedder import Embedder
            self._embedder = Embedder(model_name=settings.embed_model)
        vec = self._embedder.encode([query])
        return vec[0].tolist()

    def semantic_search(
        self,
        query: str,
        k: Optional[int] = None,
        source: Optional[str] = None,
        sentiment: Optional[str] = None,
        topic_id: Optional[int] = None,
        discovery_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """Natural-language search over review embeddings."""
        k = k or settings.default_search_k
        where: Dict[str, Any] = {}
        if source:
            where["source"] = source
        if sentiment:
            where["sentiment"] = sentiment
        if topic_id is not None:
            where["topic_id"] = int(topic_id)
        if discovery_only:
            where["discovery_related"] = True

        embedding = self._embed_query(query)
        hits = self.vector.search(embedding, k=k, where=where or None)

        if not hits:
            return hits

        ids = [h["review_id"] for h in hits]
        placeholders = ", ".join(["?"] * len(ids))
        detail = self.warehouse.fetchdf(
            f"""
            SELECT review_id, source, sentiment, segment, pain_category,
                   discovery_related, topic_id, topic_label, verbatim_quote, unmet_need
            FROM reviews_enriched
            WHERE review_id IN ({placeholders})
            """,
            ids,
        )
        detail_map = {r["review_id"]: r for _, r in detail.iterrows()}

        for hit in hits:
            rid = hit["review_id"]
            if rid in detail_map:
                hit["detail"] = detail_map[rid].to_dict()
        return hits

    def filter_reviews(
        self,
        source: Optional[str] = None,
        sentiment: Optional[str] = None,
        segment: Optional[str] = None,
        topic_id: Optional[int] = None,
        discovery_only: bool = False,
        limit: int = 50,
    ) -> pd.DataFrame:
        """Structured filter over the enriched reviews table."""
        clauses = ["1=1"]
        params: List[Any] = []

        if source:
            clauses.append("source = ?")
            params.append(source)
        if sentiment:
            clauses.append("sentiment = ?")
            params.append(sentiment)
        if segment:
            clauses.append("segment = ?")
            params.append(segment)
        if topic_id is not None:
            clauses.append("topic_id = ?")
            params.append(int(topic_id))
        if discovery_only:
            clauses.append("discovery_related = TRUE")

        sql = f"""
            SELECT review_id, source, sentiment, segment, pain_category,
                   discovery_related, topic_id, topic_label, verbatim_quote
            FROM reviews_enriched
            WHERE {" AND ".join(clauses)}
            LIMIT ?
        """
        params.append(limit)
        return self.warehouse.fetchdf(sql, params)

    def list_cards(
        self,
        severity: Optional[str] = None,
        theme: Optional[str] = None,
        min_priority: Optional[float] = None,
        limit: int = 20,
    ) -> pd.DataFrame:
        """Return insight cards ranked by priority."""
        clauses = ["1=1"]
        params: List[Any] = []

        if severity:
            clauses.append("LOWER(severity) = ?")
            params.append(severity.lower())
        if theme:
            clauses.append("LOWER(theme) LIKE ?")
            params.append(f"%{theme.lower()}%")
        if min_priority is not None:
            clauses.append("priority_score >= ?")
            params.append(float(min_priority))

        sql = f"""
            SELECT insight_id, topic_id, title, theme, severity, trend,
                   priority_score, supporting_review_count, discovery_share_pct,
                   suggested_opportunity
            FROM insight_cards
            WHERE {" AND ".join(clauses)}
            ORDER BY priority_score DESC
            LIMIT ?
        """
        params.append(limit)
        return self.warehouse.fetchdf(sql, params)

    def get_card(self, insight_id: str) -> Optional[Dict[str, Any]]:
        df = self.warehouse.fetchdf(
            "SELECT * FROM insight_cards WHERE insight_id = ?",
            [insight_id],
        )
        if df.empty:
            return None
        return df.iloc[0].to_dict()

    def get_topic(self, topic_id: int) -> Optional[Dict[str, Any]]:
        df = self.warehouse.fetchdf(
            "SELECT * FROM topics WHERE topic_id = ?",
            [int(topic_id)],
        )
        if df.empty:
            return None
        return df.iloc[0].to_dict()

    def stats(self) -> Dict[str, Any]:
        """High-level counts for dashboards."""
        tables = ["raw_reviews", "insights", "reviews_enriched", "topics", "insight_cards"]
        counts = {}
        for t in tables:
            try:
                counts[t] = int(
                    self.warehouse.fetchdf(f"SELECT COUNT(*) AS n FROM {t}").iloc[0]["n"]
                )
            except Exception:
                counts[t] = 0
        try:
            counts["vectors"] = self.vector.count
        except Exception:
            counts["vectors"] = 0
        return counts

    def close(self) -> None:
        self.warehouse.close()
