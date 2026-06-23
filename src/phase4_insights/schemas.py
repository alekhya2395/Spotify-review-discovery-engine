"""Schemas for Phase 4 PM-ready insight cards."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Severity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Trend(str, Enum):
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"
    UNKNOWN = "unknown"


class InsightCard(BaseModel):
    """One PM-actionable insight synthesized from a Phase-3 topic cluster."""

    model_config = ConfigDict(
        use_enum_values=True,
        str_strip_whitespace=True,
        extra="ignore",
    )

    insight_id: str = Field(..., description="Stable id, e.g. INS-007")
    topic_id: int = Field(..., description="Foreign key to Phase-3 topic_id")
    title: str = Field(..., max_length=200)
    theme: str = Field(..., description="Human-readable theme bucket")
    narrative: str = Field(
        ...,
        description="2-3 sentence summary of the user pain / opportunity.",
        max_length=1200,
    )
    severity: Severity
    trend: Trend
    priority_score: float = Field(..., ge=0.0, le=100.0)

    affected_segments: List[str] = Field(default_factory=list)
    top_unmet_needs: List[str] = Field(default_factory=list)
    evidence_quotes: List[str] = Field(default_factory=list)
    evidence_review_ids: List[str] = Field(default_factory=list)

    supporting_review_count: int = Field(..., ge=0)
    discovery_share_pct: float = Field(..., ge=0.0, le=100.0)
    negative_share_pct: float = Field(..., ge=0.0, le=100.0)
    top_sources: List[str] = Field(default_factory=list)
    top_pain_category: str = Field(default="other")

    suggested_opportunity: str = Field(..., max_length=500)
    segment_notes: Optional[str] = Field(
        default=None,
        description="How pain differs across segments (if signal exists).",
        max_length=600,
    )

    model_used: str = Field(default="rule-based")
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    @field_validator("generated_at")
    @classmethod
    def _ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)


INSIGHT_CARD_CSV_COLUMNS = [
    "insight_id",
    "topic_id",
    "title",
    "theme",
    "narrative",
    "severity",
    "trend",
    "priority_score",
    "affected_segments",
    "top_unmet_needs",
    "evidence_quotes",
    "evidence_review_ids",
    "supporting_review_count",
    "discovery_share_pct",
    "negative_share_pct",
    "top_sources",
    "top_pain_category",
    "suggested_opportunity",
    "segment_notes",
    "model_used",
    "generated_at",
]


class TopicBundle(BaseModel):
    """Aggregated context for one cluster — fed to the LLM and fallback generator."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    topic_id: int
    label: str
    size: int
    share_pct: float
    discovery_share_pct: float
    top_pain_category: str
    top_sentiment: str
    top_segment: str
    keywords: List[str] = Field(default_factory=list)
    top_sources: List[str] = Field(default_factory=list)

    sentiment_breakdown: dict = Field(default_factory=dict)
    segment_breakdown: dict = Field(default_factory=dict)
    pain_breakdown: dict = Field(default_factory=dict)
    source_breakdown: dict = Field(default_factory=dict)

    unmet_needs: List[str] = Field(default_factory=list)
    evidence_quotes: List[str] = Field(default_factory=list)
    evidence_review_ids: List[str] = Field(default_factory=list)

    negative_share_pct: float = 0.0
    trend: Trend = Trend.UNKNOWN
    trend_detail: str = ""
