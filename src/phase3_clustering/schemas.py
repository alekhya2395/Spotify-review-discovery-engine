"""Schemas for Phase 3 (clustering & topic modeling).

A `Topic` row is the unit of output: one cluster of semantically similar
reviews, enriched with keywords, representative quotes, distribution stats,
and an optional LLM-generated human label.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Topic(BaseModel):
    """One topic / cluster discovered by BERTopic."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="ignore",
    )

    topic_id: int = Field(
        ..., description="BERTopic id. -1 means 'unclustered noise'."
    )
    label: str = Field(
        ..., description="Human-friendly topic name (LLM-generated or keyword-derived)."
    )
    keywords: List[str] = Field(
        default_factory=list,
        description="Top c-TF-IDF keywords ranked by importance.",
    )
    size: int = Field(..., ge=0, description="Number of reviews in this cluster.")
    share_pct: float = Field(
        ..., ge=0.0, le=100.0, description="Cluster size as a percentage of all clustered reviews."
    )

    discovery_share_pct: float = Field(
        ..., ge=0.0, le=100.0,
        description="Of this cluster's reviews, what % are flagged discovery_related.",
    )
    top_pain_category: str = Field(
        ..., description="Most common Phase-2 pain_category in this cluster."
    )
    top_sentiment: str = Field(
        ..., description="Most common Phase-2 sentiment in this cluster."
    )
    top_segment: str = Field(
        ..., description="Most common Phase-2 user segment in this cluster."
    )
    top_sources: List[str] = Field(
        default_factory=list,
        description="Top originating sources (e.g. play_store, reddit), ranked.",
    )

    representative_quotes: List[str] = Field(
        default_factory=list,
        description="A handful of verbatim quotes that best summarize the cluster.",
    )
    representative_review_ids: List[str] = Field(
        default_factory=list,
        description="Foreign keys for the representative quotes.",
    )

    embedding_model: str = Field(..., description="Embedding model id used for clustering.")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this topic was computed.",
    )

    @field_validator("created_at")
    @classmethod
    def _ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)


TOPIC_CSV_COLUMNS = [
    "topic_id",
    "label",
    "size",
    "share_pct",
    "discovery_share_pct",
    "top_pain_category",
    "top_sentiment",
    "top_segment",
    "top_sources",
    "keywords",
    "representative_quotes",
    "representative_review_ids",
    "embedding_model",
    "created_at",
]


INSIGHT_WITH_TOPIC_CSV_COLUMNS = [
    "review_id",
    "source",
    "discovery_related",
    "pain_category",
    "sentiment",
    "segment",
    "unmet_need",
    "verbatim_quote",
    "confidence",
    "topic_id",
    "topic_label",
    "topic_probability",
]


class TopicAssignment(BaseModel):
    """Per-review cluster assignment (joined onto the insights table)."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    review_id: str
    topic_id: int
    topic_label: str
    topic_probability: Optional[float] = Field(default=None, ge=0.0, le=1.0)
