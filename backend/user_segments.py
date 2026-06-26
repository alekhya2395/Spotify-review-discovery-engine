"""User-segment classification with per-segment frustration/challenge/need.

Each review may belong to ZERO, ONE, or MULTIPLE segments. Classification
combines the structured ``listening_style`` field with substring matches on
the wider review text so we don't depend on a single sparse column.

Six product-defined segments are reported:

    1. Discovery Seeker  — actively wants to find new music
    2. Playlist User     — relies on curated playlists / Discover Weekly
    3. Heavy Listener    — listens daily / long sessions
    4. Casual Listener   — occasional / passive listening
    5. Premium User      — paid tier
    6. Free User         — ad-supported tier

For each segment we surface:
    - count, share_of_corpus, sentiment mix
    - Primary frustration (top pain category)
    - Discovery challenge (top discovery-struggle phrase that overlaps the segment)
    - Unmet need (top inferred ``unmet_need`` phrase)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any
import sys

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent))

from data_loader import load_insights_df  # noqa: E402
from format_labels import format_pain  # noqa: E402


@dataclass(frozen=True)
class SegmentRule:
    name: str
    description: str
    style_values: tuple[str, ...]
    keywords: tuple[str, ...]


_SEGMENTS: tuple[SegmentRule, ...] = (
    SegmentRule(
        name="Discovery Seeker",
        description="Listeners who actively want to find new music, artists, or genres.",
        style_values=("genre_specific",),
        keywords=(
            "discover", "discovery", "explore", "exploration",
            "find new", "new music", "new artist", "new artists",
            "fresh music", "fresher", "diverse", "diversity",
            "broaden", "broader",
        ),
    ),
    SegmentRule(
        name="Playlist User",
        description="Listeners whose primary surface is curated playlists or auto-mixes.",
        style_values=(),
        keywords=(
            "playlist", "playlists",
            "discover weekly", "release radar", "daily mix",
            "made for you", "curated", "curator",
            "my mix", "this is", "wrapped",
        ),
    ),
    SegmentRule(
        name="Heavy Listener",
        description="High-frequency listeners with long, frequent sessions.",
        style_values=("heavy", "long_term"),
        keywords=(
            "all day", "every day", "everyday",
            "hours", "hour each",
            "always listen", "always listening", "listen non-stop",
            "non-stop", "non stop",
            "constantly listen", "constantly playing",
            "for years",
            "long-time user", "long time user",
            "heavy user",
        ),
    ),
    SegmentRule(
        name="Casual Listener",
        description="Occasional or passive listeners who don't fine-tune the experience.",
        style_values=("casual", "new_user"),
        keywords=(
            "casual", "casually",
            "sometimes listen", "occasionally",
            "once in a while",
            "barely use", "barely listen",
            "just started", "new to spotify", "new user",
            "background music",
            "passive listen",
        ),
    ),
    SegmentRule(
        name="Premium User",
        description="Paying subscribers (Premium / Family / Duo / Student).",
        style_values=("premium",),
        keywords=(
            "premium",
            "paid subscription", "paid plan", "paying customer", "paying user",
            "family plan", "duo plan", "student plan",
            "subscription",
        ),
    ),
    SegmentRule(
        name="Free User",
        description="Ad-supported free-tier listeners.",
        style_values=("free",),
        keywords=(
            "free version", "free tier", "free plan",
            "free user", "free account",
            "ads", "advert", "advertisement",
            "without paying", "can't afford premium", "cannot afford premium",
        ),
    ),
)


_EMPTY = {"", "none", "nan", "null", "n/a", "na", "unknown"}


def _percent(n: int, denom: int) -> str:
    if not denom:
        return ""
    return f"{round(100.0 * n / denom, 1)}%"


def _row_text(row: pd.Series) -> str:
    parts: list[str] = []
    for col in ("unmet_need", "user_suggested_fix", "specific_pain", "verbatim_quote", "pain_category", "listening_style"):
        val = row.get(col)
        if val is None:
            continue
        try:
            if isinstance(val, float) and pd.isna(val):
                continue
        except TypeError:
            pass
        text = str(val).strip()
        if text and text.lower() not in _EMPTY:
            parts.append(text)
    return " ".join(parts)


def _mask_for_segment(df: pd.DataFrame, text_blobs: pd.Series, rule: SegmentRule) -> pd.Series:
    mask = pd.Series(False, index=df.index)
    if rule.style_values and "listening_style" in df.columns:
        style_lower = df["listening_style"].astype(str).str.lower().str.strip()
        mask = mask | style_lower.isin({s.lower() for s in rule.style_values})
    for kw in rule.keywords:
        if not kw:
            continue
        mask = mask | text_blobs.str.contains(kw.lower(), regex=False, na=False)
    return mask


def _primary_frustration(slice_df: pd.DataFrame) -> dict[str, Any] | None:
    if slice_df.empty or "pain_category" not in slice_df.columns:
        return None
    sentiment = slice_df.get("sentiment")
    if sentiment is not None:
        sent_lower = sentiment.astype(str).str.lower()
        sub = slice_df[sent_lower.isin({"negative", "mixed"})]
    else:
        sub = slice_df
    pool = sub if not sub.empty else slice_df
    series = pool["pain_category"].astype(str).str.lower().str.strip()
    series = series[~series.isin(_EMPTY)]
    if series.empty:
        return None
    counts = series.value_counts()
    key = str(counts.index[0])
    count = int(counts.iloc[0])
    return {
        "key": key,
        "label": format_pain(key),
        "count": count,
        "share_of_segment": _percent(count, int(len(slice_df))),
    }


def _top_unmet_need(slice_df: pd.DataFrame) -> dict[str, Any] | None:
    if slice_df.empty or "unmet_need" not in slice_df.columns:
        return None
    series = slice_df["unmet_need"].astype(str).str.strip()
    series = series[~series.str.lower().isin(_EMPTY)]
    if series.empty:
        return None
    counts = series.value_counts()
    label = str(counts.index[0])
    count = int(counts.iloc[0])
    return {
        "label": label.rstrip("."),
        "count": count,
        "share_of_segment": _percent(count, int(len(slice_df))),
    }


_DISCOVERY_CHALLENGE_PHRASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Hard to find new artists or genres",
        (
            "guided music discovery",
            "easier music discovery",
            "easy to discover",
            "easy to find new",
            "hard to find new",
            "hard to discover",
            "find new artists",
            "discover new artists",
            "new genre",
        ),
    ),
    (
        "Discover Weekly / curated playlists feel stale",
        (
            "stronger curated discovery",
            "curated discovery playlists",
            "fresher and more accurate",
            "stale discover weekly",
            "stale playlist",
            "discover weekly is repetitive",
            "discover weekly feels stale",
            "release radar",
            "daily mix",
        ),
    ),
    (
        "Recommendations feel irrelevant",
        (
            "better personalization",
            "irrelevant recommendation",
            "wrong recommendation",
            "doesn't understand my taste",
            "doesn't get me",
            "off target",
        ),
    ),
    (
        "Algorithm reinforces what users already listen to",
        (
            "more diverse recommendations",
            "diverse recommendations",
            "less repetitive",
            "echo chamber",
            "same song", "same songs",
            "same artist", "same artists",
            "over and over",
            "stuck listening",
        ),
    ),
    (
        "Ads disrupt the discovery flow",
        (
            "ads interrupt",
            "ads disrupt",
            "ads while listening",
            "ads when exploring",
            "fewer ads",
        ),
    ),
    (
        "Want more control over the algorithm",
        (
            "more control over recommend",
            "control the algorithm",
            "tune the algorithm",
            "teach the algorithm",
            "tell the algorithm",
            "algorithm doesn't learn",
        ),
    ),
)


def _top_discovery_challenge(slice_df: pd.DataFrame) -> dict[str, Any] | None:
    if slice_df.empty:
        return None
    text_blobs = slice_df.apply(_row_text, axis=1).str.lower()
    best_label: str | None = None
    best_count = 0
    for label, keywords in _DISCOVERY_CHALLENGE_PHRASES:
        mask = pd.Series(False, index=slice_df.index)
        for kw in keywords:
            mask = mask | text_blobs.str.contains(kw, regex=False, na=False)
        count = int(mask.sum())
        if count > best_count:
            best_count = count
            best_label = label
    if best_label is None or best_count == 0:
        return None
    return {
        "label": best_label,
        "count": best_count,
        "share_of_segment": _percent(best_count, int(len(slice_df))),
    }


def _sentiment_mix(slice_df: pd.DataFrame) -> dict[str, str]:
    if slice_df.empty or "sentiment" not in slice_df.columns:
        return {}
    series = slice_df["sentiment"].astype(str).str.lower().str.strip()
    series = series[~series.isin(_EMPTY)]
    if series.empty:
        return {}
    total = int(len(slice_df))
    counts = series.value_counts()
    return {str(name): _percent(int(c), total) for name, c in counts.items()}


def _build_payload(df: pd.DataFrame) -> dict[str, Any]:
    total = int(len(df))
    if df.empty:
        return {
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "total_reviews": 0,
            "segments": [],
        }

    text_blobs = df.apply(_row_text, axis=1).str.lower()
    segments: list[dict[str, Any]] = []
    for rule in _SEGMENTS:
        mask = _mask_for_segment(df, text_blobs, rule)
        count = int(mask.sum())
        if count == 0:
            segments.append({
                "name": rule.name,
                "description": rule.description,
                "count": 0,
                "share_of_corpus": _percent(0, total),
                "sentiment_mix": {},
                "primary_frustration": None,
                "discovery_challenge": None,
                "unmet_need": None,
            })
            continue
        slice_df = df[mask]
        segments.append({
            "name": rule.name,
            "description": rule.description,
            "count": count,
            "share_of_corpus": _percent(count, total),
            "sentiment_mix": _sentiment_mix(slice_df),
            "primary_frustration": _primary_frustration(slice_df),
            "discovery_challenge": _top_discovery_challenge(slice_df),
            "unmet_need": _top_unmet_need(slice_df),
        })
    return {
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "total_reviews": total,
        "segments": segments,
    }


@lru_cache(maxsize=1)
def compute_user_segments() -> dict[str, Any]:
    return _build_payload(load_insights_df())


def reset_cache() -> None:
    compute_user_segments.cache_clear()


__all__ = ["compute_user_segments", "reset_cache"]


if __name__ == "__main__":  # pragma: no cover - manual
    import json
    print(json.dumps(compute_user_segments(), indent=2, default=str)[:4000])
