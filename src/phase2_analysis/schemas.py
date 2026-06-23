"""Schemas for Phase 2 analysis.

`Insight` is the **contract** the LLM must produce per review. Downstream
phases (clustering, insight cards, dashboards) read from this schema.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class PainCategory(str, Enum):
    """Top-level theme buckets aligned with the problem statement."""

    DISCOVERY = "discovery"
    RECOMMENDATION_QUALITY = "recommendation_quality"
    LISTENING_BEHAVIOR = "listening_behavior"
    AUDIO_QUALITY = "audio_quality"
    UI_UX = "ui_ux"
    PRICING = "pricing"
    ADS = "ads"
    TECHNICAL = "technical"
    CONTENT_AVAILABILITY = "content_availability"
    PODCASTS = "podcasts"
    SOCIAL = "social"
    OTHER = "other"
    NONE = "none"


class Segment(str, Enum):
    """User segment inferred from the review text."""

    NEW_USER = "new_user"
    LONG_TERM = "long_term"
    FREE = "free"
    PREMIUM = "premium"
    CASUAL = "casual"
    HEAVY = "heavy"
    GENRE_SPECIFIC = "genre_specific"
    UNKNOWN = "unknown"


class Insight(BaseModel):
    """Structured per-review insight extracted by the LLM."""

    model_config = ConfigDict(
        use_enum_values=True,
        str_strip_whitespace=True,
        extra="ignore",
    )

    review_id: str = Field(..., description="Foreign key back to the raw review")
    source: str = Field(..., description="Originating source (app_store, reddit, etc.)")

    discovery_related: bool = Field(
        ..., description="Whether the review is about music discovery, exploration, or recommendations"
    )
    pain_category: PainCategory = Field(..., description="Primary theme bucket")
    sentiment: Sentiment = Field(..., description="Overall sentiment of the review")
    segment: Segment = Field(..., description="Inferred user segment")
    unmet_need: str = Field(
        ...,
        description="One short phrase capturing the feature request / missing capability, or 'none'.",
        max_length=300,
    )
    verbatim_quote: str = Field(
        ...,
        description="Exact substring from the original review that supports the analysis.",
        max_length=600,
    )
    confidence: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="LLM self-reported confidence (0-1)"
    )

    model_used: str = Field(..., description="LLM model id (e.g. llama-3.3-70b-versatile)")
    analyzed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this insight was generated",
    )

    @field_validator("analyzed_at")
    @classmethod
    def _ensure_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)


# Field order used for the CSV header (kept stable for downstream readers).
INSIGHT_CSV_COLUMNS = [
    "review_id",
    "source",
    "discovery_related",
    "pain_category",
    "sentiment",
    "segment",
    "unmet_need",
    "verbatim_quote",
    "confidence",
    "model_used",
    "analyzed_at",
]
