"""Append-safe CSV writer for insights.

Maintains a single rolling `data/processed/insights.csv` file. Reading the
existing CSV first lets us:
  - know which `review_id`s have already been analyzed (skip them next run)
  - append new rows without rewriting the whole file
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, List, Set

from loguru import logger

from .config import settings
from .schemas import INSIGHT_CSV_COLUMNS, Insight


class InsightStore:
    """Filesystem-backed insights CSV. Swap with Postgres/DuckDB in production."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else settings.insights_csv_path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def existing_review_ids(self) -> Set[str]:
        """Return the set of `review_id`s already present in the CSV."""
        if not self.path.exists():
            return set()
        ids: Set[str] = set()
        try:
            with self.path.open("r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rid = (row.get("review_id") or "").strip()
                    if rid:
                        ids.add(rid)
        except OSError as exc:
            logger.warning("[insight-store] could not read {p}: {e}", p=self.path, e=exc)
            return set()
        logger.info("[insight-store] {n} review_ids already analyzed", n=len(ids))
        return ids

    def append(self, insights: Iterable[Insight]) -> int:
        """Append insights to the CSV; create header on first write."""
        rows: List[dict] = []
        for ins in insights:
            row = ins.model_dump(mode="json")
            ordered = {col: row.get(col, "") for col in INSIGHT_CSV_COLUMNS}
            rows.append(ordered)

        if not rows:
            logger.warning("[insight-store] nothing to append")
            return 0

        write_header = not self.path.exists()
        try:
            with self.path.open("a", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=INSIGHT_CSV_COLUMNS, extrasaction="ignore")
                if write_header:
                    writer.writeheader()
                writer.writerows(rows)
        except OSError as exc:
            logger.error("[insight-store] write failed {p}: {e}", p=self.path, e=exc)
            return 0

        logger.info("[insight-store] appended {n} rows -> {p}", n=len(rows), p=self.path)
        return len(rows)
