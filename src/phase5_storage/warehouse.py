"""DuckDB processed warehouse — analytical store for reviews, insights, topics, cards."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import duckdb
import pandas as pd
from loguru import logger

from .config import settings


class DuckDBWarehouse:
    """Filesystem-backed DuckDB warehouse (production: swap for Postgres/BigQuery)."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else settings.warehouse_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = duckdb.connect(str(self.path))

    def close(self) -> None:
        self.conn.close()

    def rebuild(
        self,
        raw_reviews: pd.DataFrame,
        insights: pd.DataFrame,
        enriched: pd.DataFrame,
        topics: pd.DataFrame,
        cards: pd.DataFrame,
    ) -> dict:
        """Drop and reload all tables. Returns row counts per table."""
        topics_flat = topics.copy()
        for col in ("keywords", "representative_quotes", "representative_review_ids", "top_sources"):
            if col in topics_flat.columns:
                topics_flat[col] = topics_flat[col].apply(
                    lambda x: " || ".join(x) if isinstance(x, list) else str(x)
                )

        cards_flat = cards.copy()
        for col in (
            "affected_segments",
            "top_unmet_needs",
            "evidence_quotes",
            "evidence_review_ids",
            "top_sources",
        ):
            if col in cards_flat.columns:
                cards_flat[col] = cards_flat[col].apply(
                    lambda x: " || ".join(x) if isinstance(x, list) else str(x)
                )

        tables = {
            "raw_reviews": raw_reviews,
            "insights": insights,
            "reviews_enriched": enriched,
            "topics": topics_flat,
            "insight_cards": cards_flat,
        }

        counts = {}
        for name, df in tables.items():
            self.conn.execute(f"DROP TABLE IF EXISTS {name}")
            if df is not None and not df.empty:
                self.conn.register("_tmp_df", df)
                self.conn.execute(f"CREATE TABLE {name} AS SELECT * FROM _tmp_df")
                self.conn.unregister("_tmp_df")
                counts[name] = len(df)
            else:
                counts[name] = 0

        # Convenience view: cards joined to topics
        self.conn.execute("DROP VIEW IF EXISTS v_cards_with_topics")
        self.conn.execute(
            """
            CREATE VIEW v_cards_with_topics AS
            SELECT c.*, t.label AS topic_label, t.keywords AS topic_keywords
            FROM insight_cards c
            LEFT JOIN topics t ON c.topic_id = t.topic_id
            """
        )

        logger.info("[warehouse] rebuilt DuckDB at {p} | counts={c}", p=self.path, c=counts)
        return counts

    def execute(self, sql: str, params=None):
        if params:
            return self.conn.execute(sql, params)
        return self.conn.execute(sql)

    def fetchdf(self, sql: str, params=None) -> pd.DataFrame:
        if params:
            return self.conn.execute(sql, params).fetchdf()
        return self.conn.execute(sql).fetchdf()
