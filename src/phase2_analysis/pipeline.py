"""Phase 2 orchestrator.

Steps:
  1. Init Groq client + load reviews already analyzed (CSV)
  2. Read all JSONL from `data/raw/`, drop reviews already analyzed
  3. Optionally cap total reviews per run
  4. Send to Groq in batches of `GROQ_BATCH_SIZE`
  5. Append validated insights to `data/processed/insights.csv`
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional

from loguru import logger

from .analyzer import Analyzer
from .config import settings
from .groq_client import GroqClient
from .loader import load_all_reviews
from .storage import InsightStore
from .utils import setup_logging


@dataclass
class AnalysisSummary:
    started_at: str
    finished_at: str
    duration_seconds: float
    reviews_considered: int
    reviews_already_analyzed: int
    reviews_sent_to_llm: int
    insights_written: int
    model_used: str
    csv_path: str


class AnalysisPipeline:
    """Coordinates loader, Groq client, analyzer, and CSV store for one run."""

    def __init__(
        self,
        client: Optional[GroqClient] = None,
        store: Optional[InsightStore] = None,
        max_reviews: Optional[int] = None,
    ) -> None:
        setup_logging()
        self.client = client or GroqClient()
        self.analyzer = Analyzer(client=self.client)
        self.store = store or InsightStore()
        self.max_reviews = (
            max_reviews
            if max_reviews is not None
            else settings.max_reviews_per_analysis_run
        )

    def run(self) -> AnalysisSummary:
        started = datetime.now(timezone.utc)

        already = self.store.existing_review_ids()
        reviews = load_all_reviews(skip_ids=already)
        considered = len(reviews) + len(already)

        if self.max_reviews and self.max_reviews > 0 and len(reviews) > self.max_reviews:
            logger.warning(
                "[pipeline] capping {n} -> {c} (MAX_REVIEWS_PER_ANALYSIS_RUN)",
                n=len(reviews),
                c=self.max_reviews,
            )
            reviews = reviews[: self.max_reviews]

        written = 0
        if not reviews:
            logger.info("[pipeline] nothing new to analyze")
        else:
            # Flush each batch to disk the instant it completes — no in-memory
            # accumulation means a rate-limit or Ctrl-C never loses progress.
            def _on_batch(batch_insights):
                nonlocal written
                written += self.store.append(batch_insights)

            self.analyzer.analyze(reviews, on_batch=_on_batch)
        finished = datetime.now(timezone.utc)

        summary = AnalysisSummary(
            started_at=started.isoformat(),
            finished_at=finished.isoformat(),
            duration_seconds=(finished - started).total_seconds(),
            reviews_considered=considered,
            reviews_already_analyzed=len(already),
            reviews_sent_to_llm=len(reviews),
            insights_written=written,
            model_used=self.client.model,
            csv_path=str(self.store.path),
        )

        logger.info(
            "[pipeline] done in {d:.1f}s | sent={s} | insights={i} | csv={p}",
            d=summary.duration_seconds,
            s=summary.reviews_sent_to_llm,
            i=summary.insights_written,
            p=summary.csv_path,
        )
        return summary

    @staticmethod
    def summary_to_dict(summary: AnalysisSummary) -> dict:
        return asdict(summary)
