"""Phase 4 orchestrator — synthesize PM-ready insight cards from Phase-3 clusters."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import List, Optional, Set

from loguru import logger

from .aggregator import ThemeAggregator
from .config import settings
from .generator import CardGenerator
from .loader import load_review_timestamps, load_topics_and_insights
from .scorer import score_bundles
from .storage import InsightCardStore
from .utils import setup_logging


@dataclass
class GenerationSummary:
    started_at: str
    finished_at: str
    duration_seconds: float
    topics_on_disk: int
    bundles_built: int
    cards_generated: int
    llm_cards: int
    rule_based_cards: int
    model_used: str
    csv_path: str
    json_path: str
    top_insight_id: str
    top_priority_score: float


class GenerationPipeline:
    """End-to-end Phase-4 run."""

    def __init__(
        self,
        aggregator: Optional[ThemeAggregator] = None,
        generator: Optional[CardGenerator] = None,
        store: Optional[InsightCardStore] = None,
        use_llm: Optional[bool] = None,
        model: Optional[str] = None,
    ) -> None:
        setup_logging()
        self.aggregator = aggregator or ThemeAggregator()
        self.generator = generator or CardGenerator(use_llm=use_llm, model=model)
        self.store = store or InsightCardStore()

    def run(self) -> GenerationSummary:
        started = datetime.now(timezone.utc)

        topics_df, insights_df = load_topics_and_insights()

        review_ids: Set[str] = set(insights_df["review_id"].astype(str).tolist())
        timestamps = load_review_timestamps(review_ids)

        bundles = self.aggregator.build_bundles(topics_df, insights_df, timestamps)
        if not bundles:
            raise RuntimeError(
                "No topic bundles to synthesize. Re-run Phase 3 or lower MIN_TOPIC_SIZE."
            )

        priority_scores = score_bundles(bundles)
        cards = self.generator.generate_all(bundles, priority_scores)
        self.store.write(cards)

        finished = datetime.now(timezone.utc)
        llm_count = sum(1 for c in cards if c.model_used != "rule-based")
        top = max(cards, key=lambda c: c.priority_score)

        summary = GenerationSummary(
            started_at=started.isoformat(),
            finished_at=finished.isoformat(),
            duration_seconds=(finished - started).total_seconds(),
            topics_on_disk=len(topics_df),
            bundles_built=len(bundles),
            cards_generated=len(cards),
            llm_cards=llm_count,
            rule_based_cards=len(cards) - llm_count,
            model_used=self.generator.model if llm_count else "rule-based",
            csv_path=str(self.store.csv_path),
            json_path=str(self.store.json_path),
            top_insight_id=top.insight_id,
            top_priority_score=top.priority_score,
        )
        logger.info(
            "[pipeline] done in {d:.1f}s | cards={c} (llm={l}, rule={r})",
            d=summary.duration_seconds,
            c=summary.cards_generated,
            l=summary.llm_cards,
            r=summary.rule_based_cards,
        )
        return summary

    @staticmethod
    def summary_to_dict(summary: GenerationSummary) -> dict:
        return asdict(summary)
