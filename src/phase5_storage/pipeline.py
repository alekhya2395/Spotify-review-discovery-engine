"""Phase 5 orchestrator — build warehouse, vector index, and metadata catalog."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional

from loguru import logger

from .catalog import MetadataCatalog
from .config import settings
from .loaders import (
    build_enriched_reviews,
    load_embeddings,
    load_insight_cards,
    load_insights_deduped,
    load_insights_with_topics,
    load_raw_reviews,
    load_topics,
)
from .utils import setup_logging
from .vector_index import VectorIndex
from .warehouse import DuckDBWarehouse


@dataclass
class IndexingSummary:
    started_at: str
    finished_at: str
    duration_seconds: float
    warehouse_path: str
    chroma_path: str
    catalog_path: str
    raw_reviews: int
    insights: int
    reviews_enriched: int
    topics: int
    insight_cards: int
    vectors_indexed: int
    catalog_run_id: int


class IndexingPipeline:
    """One end-to-end Phase-5 indexing run."""

    def __init__(
        self,
        warehouse: Optional[DuckDBWarehouse] = None,
        vector_index: Optional[VectorIndex] = None,
        catalog: Optional[MetadataCatalog] = None,
        skip_vectors: bool = False,
    ) -> None:
        setup_logging()
        settings.ensure_directories()
        self.skip_vectors = skip_vectors
        self.warehouse = warehouse
        self.vector_index = vector_index
        self.catalog = catalog or MetadataCatalog()

    def run(self) -> IndexingSummary:
        started = datetime.now(timezone.utc)

        raw_df = load_raw_reviews()
        insights_df = load_insights_deduped()
        enriched_df = load_insights_with_topics()
        topics_df = load_topics()
        cards_df = load_insight_cards()

        merged_enriched = build_enriched_reviews(raw_df, enriched_df)

        warehouse = self.warehouse or DuckDBWarehouse()
        counts = warehouse.rebuild(
            raw_reviews=raw_df,
            insights=insights_df,
            enriched=merged_enriched,
            topics=topics_df,
            cards=cards_df,
        )
        warehouse.close()

        vectors_indexed = 0
        if not self.skip_vectors:
            embeddings, index_df = load_embeddings()
            vector = self.vector_index or VectorIndex()
            vectors_indexed = vector.rebuild(
                embeddings=embeddings,
                index_df=index_df,
                documents_df=merged_enriched,
            )

        finished = datetime.now(timezone.utc)
        models = {
            "phase2_llm": os.getenv("GROQ_MODEL", "unknown"),
            "phase3_embedder": os.getenv("EMBED_MODEL", settings.embed_model),
            "phase4_llm": os.getenv("GROQ_MODEL", "unknown"),
        }
        run_id = self.catalog.record_run(
            started_at=started.isoformat(),
            finished_at=finished.isoformat(),
            duration_seconds=(finished - started).total_seconds(),
            row_counts=counts,
            vector_count=vectors_indexed,
            models=models,
        )

        summary = IndexingSummary(
            started_at=started.isoformat(),
            finished_at=finished.isoformat(),
            duration_seconds=(finished - started).total_seconds(),
            warehouse_path=str(settings.warehouse_path),
            chroma_path=str(settings.chroma_path),
            catalog_path=str(settings.catalog_path),
            raw_reviews=counts.get("raw_reviews", 0),
            insights=counts.get("insights", 0),
            reviews_enriched=counts.get("reviews_enriched", 0),
            topics=counts.get("topics", 0),
            insight_cards=counts.get("insight_cards", 0),
            vectors_indexed=vectors_indexed,
            catalog_run_id=run_id,
        )
        logger.info(
            "[pipeline] indexed in {d:.1f}s | vectors={v} | warehouse={w}",
            d=summary.duration_seconds,
            v=vectors_indexed,
            w=summary.warehouse_path,
        )
        return summary

    @staticmethod
    def summary_to_dict(summary: IndexingSummary) -> dict:
        return asdict(summary)
