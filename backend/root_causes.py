"""Root-cause analysis for every indexed review.

For each review we test substring keyword groups against the canonical
``unmet_need`` plus the wider text blob (``verbatim_quote``,
``specific_pain``, ``user_suggested_fix``, ``pain_category``).

Each cause aggregates:
    - count
    - share_of_corpus
    - pain_categories the cause is most associated with (top 3)
    - up to three short paraphrased examples (no verbatim quotes)

The catalogue is intentionally aligned with the buckets called out by the
product team (Over-personalization, Genre repetition, Playlist dependency,
Weak exploration tools) plus the other systemic causes the dataset surfaces.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable
import sys

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent))

from data_loader import load_insights_df  # noqa: E402


@dataclass(frozen=True)
class CauseRule:
    label: str
    summary: str
    keywords: tuple[str, ...]


_RULES: tuple[CauseRule, ...] = (
    CauseRule(
        "Over-personalization",
        "Algorithm leans so hard on a user's history that it stops surfacing anything unfamiliar.",
        (
            "same song", "same songs",
            "same artist", "same artists",
            "same playlist",
            "echo chamber",
            "stuck listening",
            "over and over",
            "trapped in profile",
            "trapped in history",
            "stuck in my history",
            "stuck in my profile",
            "more diverse recommendations",
            "diverse recommendations",
            "less repetitive",
            "less familiar",
            "more variety",
            "wider variety",
            "broader recommendations",
            "outside my taste",
            "outside my bubble",
            "outside my profile",
        ),
    ),
    CauseRule(
        "Genre repetition",
        "The same genre or stylistic lane keeps surfacing in recommendations, autoplay, and radio.",
        (
            "same genre",
            "only one genre",
            "limited genre",
            "narrow genre",
            "genre loop",
            "only pop", "only rock", "only hip", "only rap", "only country",
            "stuck in a genre",
            "stuck in one genre",
            "one type of music",
            "one style",
            "monoton",
            "more diverse music",
        ),
    ),
    CauseRule(
        "Playlist dependency",
        "Listeners can only discover through Discover Weekly / Release Radar / Daily Mix and have no alternatives.",
        (
            "discover weekly",
            "release radar",
            "daily mix",
            "made for you",
            "stronger curated discovery",
            "curated discovery playlist",
            "curated discovery playlists",
            "rely on playlist",
            "depend on playlist",
            "only playlist",
            "only the playlist",
            "playlist is the only",
            "playlists are the only",
        ),
    ),
    CauseRule(
        "Weak exploration tools",
        "There are not enough surfaces, controls, or settings to actively go discover something new.",
        (
            "easier music discovery",
            "easier discovery",
            "easier to discover",
            "simpler discovery",
            "better discovery",
            "guided music discovery",
            "dedicated discovery",
            "explore tab",
            "explore mode",
            "explore section",
            "exploration tab",
            "exploration surface",
            "no way to explore",
            "limited exploration",
            "no explore",
            "hard to find new",
            "hard to discover",
            "find new artists",
            "discover new artists",
        ),
    ),
    CauseRule(
        "Feedback signals don't tune the algorithm",
        "Skipping, disliking, or saving songs does not visibly change future recommendations.",
        (
            "skip but still",
            "skipping doesn't",
            "skipping does not",
            "skip doesn't",
            "skipped but it keeps",
            "algorithm doesn't learn",
            "algorithm does not learn",
            "algorithm won't learn",
            "doesn't adapt",
            "tell the algorithm",
            "teach the algorithm",
            "tune the algorithm",
            "control the algorithm",
            "more control over recommend",
            "more control over the algorithm",
            "not interested button",
            "doesn't understand my taste",
            "doesn't understand me",
            "doesn't get my taste",
            "doesn't get me",
        ),
    ),
    CauseRule(
        "Mainstream bias",
        "Recommendations skew toward chart hits at the expense of indie, regional, and niche catalogues.",
        (
            "too mainstream",
            "only mainstream",
            "always mainstream",
            "top 40",
            "only popular",
            "no indie",
            "no jazz",
            "no classical",
            "no underground",
            "regional music",
            "regional artists",
            "regional language",
            "niche genre",
        ),
    ),
    CauseRule(
        "Ad disruption (free tier)",
        "Free-tier ads break the listening flow and undermine intentional exploration.",
        (
            "ads interrupt",
            "ads disrupt",
            "ads break",
            "ad in the middle",
            "ad break",
            "ads while listening",
            "ads while exploring",
            "free tier ads",
            "fewer ads",
            "no ads",
            "less interruptive free",
            "too many ads",
            "ads everywhere",
        ),
    ),
    CauseRule(
        "Pricing & value friction",
        "Cost, billing, or paywalled features block users from getting the experience they expect.",
        (
            "too expensive",
            "expensive",
            "raise the price",
            "price hike",
            "price increase",
            "subscription cost",
            "family plan",
            "student plan",
            "duo plan",
            "premium price",
            "worth the price",
            "value for money",
            "billing issue",
            "charged me",
        ),
    ),
    CauseRule(
        "Catalog gaps",
        "Specific tracks, albums, or local artists are missing or unavailable in the user's market.",
        (
            "missing songs",
            "missing albums",
            "missing artist",
            "not available",
            "not in my country",
            "regional catalog",
            "regional catalogue",
            "incomplete catalog",
            "incomplete catalogue",
            "remove song",
            "add missing songs",
        ),
    ),
    CauseRule(
        "Performance & stability",
        "Crashes, lag, sync issues, or login failures interrupt listening before discovery can happen.",
        (
            "crash", "crashes", "crashing",
            "lag", "laggy",
            "freeze", "freezes", "freezing",
            "buffering",
            "doesn't open",
            "won't open",
            "won't load",
            "won't play",
            "won't connect",
            "keeps disconnecting",
            "bug", "bugs",
            "glitch", "glitches",
            "login issue",
            "sign in issue",
        ),
    ),
    CauseRule(
        "UI / navigation friction",
        "Layout, search, or settings make it slow or confusing to act on a listening intent.",
        (
            "hard to navigate",
            "confusing ui",
            "confusing interface",
            "bad ui",
            "bad layout",
            "redesign",
            "new design is bad",
            "i hate the new design",
            "search is bad",
            "search doesn't work",
            "menu is confusing",
        ),
    ),
)


_EMPTY = {"", "none", "nan", "null", "n/a", "na", "unknown"}


def _row_text(row: pd.Series) -> str:
    parts: list[str] = []
    for col in ("unmet_need", "user_suggested_fix", "specific_pain", "verbatim_quote", "pain_category"):
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


def _example_from_row(row: pd.Series) -> str:
    for col in ("unmet_need", "user_suggested_fix", "specific_pain"):
        val = row.get(col)
        if val is None:
            continue
        try:
            if isinstance(val, float) and pd.isna(val):
                continue
        except TypeError:
            pass
        text = str(val).strip().rstrip(".")
        if text and text.lower() not in _EMPTY:
            return text[:160]
    return ""


def _percent(n: int, denom: int) -> str:
    if not denom:
        return ""
    return f"{round(100.0 * n / denom, 1)}%"


def _top_pain_categories(slice_df: pd.DataFrame, limit: int = 3) -> list[dict[str, Any]]:
    if slice_df.empty or "pain_category" not in slice_df.columns:
        return []
    series = slice_df["pain_category"].astype(str).str.lower().str.strip()
    series = series[~series.isin(_EMPTY)]
    if series.empty:
        return []
    counts = series.value_counts().head(limit)
    out: list[dict[str, Any]] = []
    total = int(len(slice_df))
    for key, n in counts.items():
        out.append({
            "key": str(key),
            "count": int(n),
            "share_of_cause": _percent(int(n), total),
        })
    return out


def _build_payload(df: pd.DataFrame) -> dict[str, Any]:
    total = int(len(df))
    if df.empty:
        return {
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "total_reviews": 0,
            "causes": [],
        }

    text_blobs = df.apply(_row_text, axis=1).str.lower()
    examples_pool = df.apply(_example_from_row, axis=1)

    causes: list[dict[str, Any]] = []
    for rule in _RULES:
        mask = pd.Series(False, index=df.index)
        for kw in rule.keywords:
            if not kw:
                continue
            mask = mask | text_blobs.str.contains(kw.lower(), regex=False, na=False)
        count = int(mask.sum())
        if count == 0:
            continue
        slice_df = df[mask]
        examples: list[str] = []
        for idx in slice_df.index:
            example = examples_pool.loc[idx]
            if example and example not in examples:
                examples.append(example)
            if len(examples) >= 3:
                break
        causes.append({
            "label": rule.label,
            "summary": rule.summary,
            "count": count,
            "share_of_corpus": _percent(count, total),
            "top_pain_categories": _top_pain_categories(slice_df),
            "examples": examples,
        })

    causes.sort(key=lambda c: c["count"], reverse=True)
    return {
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "total_reviews": total,
        "causes": causes,
    }


@lru_cache(maxsize=1)
def compute_root_causes() -> dict[str, Any]:
    return _build_payload(load_insights_df())


def reset_cache() -> None:
    compute_root_causes.cache_clear()


__all__ = ["compute_root_causes", "reset_cache"]


if __name__ == "__main__":  # pragma: no cover - manual
    import json
    print(json.dumps(compute_root_causes(), indent=2, default=str)[:4000])
