"""Persist Phase-4 insight cards to CSV and JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

import pandas as pd
from loguru import logger

from src.phase3_clustering.storage import LIST_DELIM

from .config import settings
from .schemas import INSIGHT_CARD_CSV_COLUMNS, InsightCard


def _serialize_list(xs: List[str]) -> str:
    return LIST_DELIM.join(str(x).replace("\n", " ").strip() for x in xs if str(x).strip())


class InsightCardStore:
    """Filesystem-backed writer for PM-ready insight cards."""

    def __init__(
        self,
        csv_path: Optional[Path] = None,
        json_path: Optional[Path] = None,
    ) -> None:
        self.csv_path = Path(csv_path) if csv_path else settings.insight_cards_csv_path
        self.json_path = Path(json_path) if json_path else settings.insight_cards_json_path
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, cards: List[InsightCard]) -> tuple[int, int]:
        if not cards:
            logger.warning("[card-store] no cards to write")
            return 0, 0

        rows = []
        json_payload = []
        for card in sorted(cards, key=lambda c: -c.priority_score):
            d = card.model_dump(mode="json")
            row = dict(d)
            row["affected_segments"] = _serialize_list(card.affected_segments)
            row["top_unmet_needs"] = _serialize_list(card.top_unmet_needs)
            row["evidence_quotes"] = _serialize_list(card.evidence_quotes)
            row["evidence_review_ids"] = _serialize_list(card.evidence_review_ids)
            row["top_sources"] = _serialize_list(card.top_sources)
            rows.append({col: row.get(col, "") for col in INSIGHT_CARD_CSV_COLUMNS})
            json_payload.append(d)

        df = pd.DataFrame(rows, columns=INSIGHT_CARD_CSV_COLUMNS)
        df.to_csv(self.csv_path, index=False, encoding="utf-8")
        with self.json_path.open("w", encoding="utf-8") as f:
            json.dump(json_payload, f, indent=2, ensure_ascii=False, default=str)

        logger.info(
            "[card-store] wrote {n} cards -> {csv} + {json}",
            n=len(cards),
            csv=self.csv_path,
            json=self.json_path,
        )
        return len(cards), len(cards)
