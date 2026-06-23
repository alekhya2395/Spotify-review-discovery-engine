"""Unified schema for raw reviews collected across all sources.

Every connector MUST return objects that conform to `RawReview`. This is the
contract that downstream phases (preprocessing, NLP, insight generation) rely
on. New sources can extend `source_meta` for source-specific fields without
breaking the contract.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SourceType(str, Enum):
    """Enumeration of supported review sources."""

    APP_STORE = "app_store"
    PLAY_STORE = "play_store"
    REDDIT = "reddit"
    COMMUNITY_FORUM = "community_forum"
    SOCIAL_MEDIA = "social_media"


class RawReview(BaseModel):
    """A single user feedback record, normalized across all sources."""

    model_config = ConfigDict(
        use_enum_values=True,
        str_strip_whitespace=True,
        extra="forbid",
    )

    review_id: str = Field(..., description="Deterministic ID: <source>:<native_id>")
    source: SourceType = Field(..., description="Which platform the review came from")
    source_region: Optional[str] = Field(
        default=None,
        description="Country / locale code (e.g. 'us', 'in'). None for global sources.",
    )

    text: str = Field(..., min_length=1, description="Raw user feedback text")
    title: Optional[str] = Field(default=None, description="Review headline if any")
    rating: Optional[float] = Field(
        default=None, ge=0, le=10, description="Normalized rating if applicable"
    )
    lang: Optional[str] = Field(default=None, description="Reported / detected language")

    author: Optional[str] = Field(default=None, description="Author handle (already public)")
    created_at: Optional[datetime] = Field(default=None, description="Original post timestamp (UTC)")

    url: Optional[str] = Field(default=None, description="Permalink to the original review")
    source_meta: Dict[str, Any] = Field(
        default_factory=dict,
        description="Source-specific extra fields (helpful votes, subreddit, etc.)",
    )

    collected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this record was ingested",
    )

    @field_validator("created_at", "collected_at")
    @classmethod
    def _ensure_utc(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is None:
            return None
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    @staticmethod
    def make_id(source: SourceType, native_id: str) -> str:
        """Build a deterministic ID. Uses a hash if the native ID is suspect."""
        native_id = (native_id or "").strip()
        if not native_id:
            raise ValueError("native_id must be a non-empty string")
        if len(native_id) > 80 or " " in native_id:
            native_id = hashlib.sha1(native_id.encode("utf-8")).hexdigest()[:16]
        return f"{source.value}:{native_id}"
