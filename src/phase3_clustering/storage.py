"""Persist Phase-3 outputs.

- `topics.csv`             : one row per cluster (the headline artifact)
- `insights_with_topics.csv`: full join — Phase 2 insights + topic_id + label

List-of-string fields are serialized with a `||` separator so Excel / Pandas
can round-trip without quoting headaches. JSON is overkill for a flat CSV.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional

import pandas as pd
from loguru import logger

from .config import settings
from .schemas import (
    INSIGHT_WITH_TOPIC_CSV_COLUMNS,
    TOPIC_CSV_COLUMNS,
    Topic,
    TopicAssignment,
)


LIST_DELIM = " || "


def _serialize_list(xs: Iterable[str]) -> str:
    return LIST_DELIM.join(str(x).replace("\n", " ").strip() for x in xs)


class TopicStore:
    """Filesystem-backed writer for Phase 3's two output tables."""

    def __init__(
        self,
        topics_csv_path: Optional[Path] = None,
        insights_with_topics_csv_path: Optional[Path] = None,
    ) -> None:
        self.topics_path = Path(topics_csv_path) if topics_csv_path else settings.topics_csv_path
        self.insights_with_topics_path = (
            Path(insights_with_topics_csv_path)
            if insights_with_topics_csv_path
            else settings.insights_with_topics_csv_path
        )
        self.topics_path.parent.mkdir(parents=True, exist_ok=True)
        self.insights_with_topics_path.parent.mkdir(parents=True, exist_ok=True)

    def write_topics(self, topics: List[Topic]) -> int:
        rows = []
        for t in topics:
            d = t.model_dump(mode="json")
            d["keywords"] = _serialize_list(t.keywords)
            d["representative_quotes"] = _serialize_list(t.representative_quotes)
            d["representative_review_ids"] = _serialize_list(t.representative_review_ids)
            d["top_sources"] = _serialize_list(t.top_sources)
            rows.append({col: d.get(col, "") for col in TOPIC_CSV_COLUMNS})

        df = pd.DataFrame(rows, columns=TOPIC_CSV_COLUMNS)
        df.to_csv(self.topics_path, index=False, encoding="utf-8")
        logger.info("[topic-store] wrote {n} topics -> {p}", n=len(df), p=self.topics_path)
        return len(df)

    def write_insights_with_topics(
        self,
        insights_df: pd.DataFrame,
        assignments: List[TopicAssignment],
    ) -> int:
        """Join Phase-2 insights with their topic assignment and dump to CSV."""
        if insights_df.empty:
            logger.warning("[topic-store] no insights to write")
            return 0

        # The pipeline may have already attached `topic_id` / `topic_probability`
        # to insights_df. Drop them so the merge re-attaches them from the
        # authoritative assignments table (avoiding `topic_id_x` / `topic_id_y`).
        left = insights_df.drop(
            columns=[c for c in ("topic_id", "topic_label", "topic_probability") if c in insights_df.columns]
        )

        assign_df = pd.DataFrame([a.model_dump(mode="json") for a in assignments])
        merged = left.merge(assign_df, on="review_id", how="left")

        for col in INSIGHT_WITH_TOPIC_CSV_COLUMNS:
            if col not in merged.columns:
                merged[col] = pd.NA

        merged["topic_id"] = pd.to_numeric(merged["topic_id"], errors="coerce").fillna(-1).astype(int)
        merged["topic_label"] = merged["topic_label"].fillna("Noise / Unclustered")
        merged["topic_probability"] = pd.to_numeric(merged["topic_probability"], errors="coerce")

        out = merged[INSIGHT_WITH_TOPIC_CSV_COLUMNS].copy()
        out.to_csv(self.insights_with_topics_path, index=False, encoding="utf-8")
        logger.info(
            "[topic-store] wrote {n} insights+topics -> {p}",
            n=len(out), p=self.insights_with_topics_path,
        )
        return len(out)
