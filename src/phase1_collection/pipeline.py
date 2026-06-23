"""Phase 1 orchestrator.

Runs each configured connector, persists results to the raw data lake, and
returns a summary that can be consumed by a scheduler (cron / Airflow).
A failure in one source never aborts the whole run.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

from loguru import logger

from .connectors import (
    AppStoreConnector,
    BaseConnector,
    CommunityForumConnector,
    PlayStoreConnector,
    RedditConnector,
    SocialMediaConnector,
)
from .schemas import SourceType
from .storage import RawDataLake, WriteResult
from .utils import setup_logging


@dataclass
class RunSummary:
    started_at: str
    finished_at: str
    duration_seconds: float
    per_source: Dict[str, dict]
    total_records: int
    total_failures: int


_DEFAULT_FACTORIES: Dict[SourceType, type[BaseConnector]] = {
    SourceType.PLAY_STORE: PlayStoreConnector,
    SourceType.APP_STORE: AppStoreConnector,
    SourceType.REDDIT: RedditConnector,
    SourceType.COMMUNITY_FORUM: CommunityForumConnector,
    SourceType.SOCIAL_MEDIA: SocialMediaConnector,
}


class CollectionPipeline:
    """Coordinates connectors, storage, and logging for a single run."""

    def __init__(
        self,
        sources: Optional[Sequence[SourceType]] = None,
        lake: Optional[RawDataLake] = None,
    ) -> None:
        setup_logging()
        self.sources = list(sources) if sources else list(_DEFAULT_FACTORIES.keys())
        self.lake = lake or RawDataLake()

    def _build_connector(self, source: SourceType) -> BaseConnector:
        factory = _DEFAULT_FACTORIES.get(source)
        if factory is None:
            raise ValueError(f"Unsupported source: {source}")
        return factory()

    def run(self) -> RunSummary:
        started = datetime.now(timezone.utc)
        per_source: Dict[str, dict] = {}
        failures = 0
        total = 0

        for source in self.sources:
            label = source.value if hasattr(source, "value") else str(source)
            try:
                connector = self._build_connector(source)
                reviews = connector.collect()
                result: WriteResult = self.lake.write(source, reviews)
                per_source[label] = {
                    "status": "ok",
                    "records_in": result.records_in,
                    "records_written": result.records_written,
                    "duplicates_dropped": result.duplicates_dropped,
                    "parquet_path": str(result.parquet_path),
                    "run_id": result.run_id,
                }
                total += result.records_written
            except Exception as exc:
                failures += 1
                logger.error("[pipeline] source={s} failed: {e}", s=label, e=exc)
                per_source[label] = {"status": "error", "error": str(exc)}

        finished = datetime.now(timezone.utc)
        summary = RunSummary(
            started_at=started.isoformat(),
            finished_at=finished.isoformat(),
            duration_seconds=(finished - started).total_seconds(),
            per_source=per_source,
            total_records=total,
            total_failures=failures,
        )
        logger.info(
            "[pipeline] done in {d:.1f}s | written={t} | failures={f}",
            d=summary.duration_seconds,
            t=summary.total_records,
            f=summary.total_failures,
        )
        return summary

    @staticmethod
    def summary_to_dict(summary: RunSummary) -> dict:
        return asdict(summary)
