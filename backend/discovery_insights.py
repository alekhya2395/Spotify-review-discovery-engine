"""Dedicated discovery insights computed from the indexed review corpus.

Four buckets are produced for every load of the dataset:

1. ``discovery_struggles``   — why users struggle to discover new music
2. ``repetition_causes``     — what drives repetitive listening behaviour
3. ``discovery_frustrations``— concrete frustrations tied to discovery
4. ``discovery_unmet_needs`` — what users wish discovery delivered

Each bucket groups similar findings under a canonical label, attaches the
review count, percentage of corpus, percentage within the relevant pool, and
up to three short paraphrased examples (verbatim quotes are NEVER returned).
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent))

from data_loader import load_insights_df  # noqa: E402
from confidence import source_counts_from_frame  # noqa: E402

# ---------------------------------------------------------------------------
# Grouping rules
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GroupRule:
    label: str
    # Substring keywords (case-insensitive) matched against unmet_need first,
    # then against the wider review text blob.
    keywords: tuple[str, ...]


_DISCOVERY_STRUGGLE_RULES: tuple[GroupRule, ...] = (
    GroupRule(
        "Algorithm reinforces what users already listen to",
        (
            "more diverse recommendations",
            "diverse recommendations",
            "less repetitive",
            "echo chamber",
            "same song", "same songs",
            "same artist", "same artists",
            "same playlist",
            "over and over",
            "stuck listening",
            "repetitive recommendation",
        ),
    ),
    GroupRule(
        "Hard to find new artists or genres",
        (
            "guided music discovery",
            "easier music discovery",
            "easy to discover",
            "easy to find new",
            "hard to find new",
            "hard to discover",
            "cannot find new",
            "can't find new",
            "find new artists",
            "discover new artists",
            "new genre",
            "underground",
            "emerging artist",
        ),
    ),
    GroupRule(
        "Recommendations feel irrelevant or off-target",
        (
            "better personalization",
            "irrelevant recommendation",
            "wrong recommendation",
            "bad recommendation",
            "poor recommendation",
            "doesn't understand my taste",
            "don't understand my taste",
            "doesn't know my taste",
            "doesn't get me",
            "off target",
            "don't match",
        ),
    ),
    GroupRule(
        "Discover Weekly / Release Radar feel stale",
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
            "made for you",
        ),
    ),
    GroupRule(
        "Limited paths to explore outside taste profile",
        (
            "dedicated discovery",
            "explore tab",
            "explore mode",
            "explore section",
            "exploration surface",
            "explore outside",
            "outside my taste",
            "break out of",
            "escape my profile",
            "comfort zone",
            "limited exploration",
        ),
    ),
    GroupRule(
        "Algorithm doesn't learn from feedback",
        (
            "tell the algorithm",
            "teach the algorithm",
            "tune the algorithm",
            "control the algorithm",
            "more control over recommend",
            "algorithm doesn't learn",
            "algorithm does not learn",
            "algorithm won't learn",
            "doesn't adapt",
            "feedback to the algorithm",
            "not interested button",
        ),
    ),
    GroupRule(
        "Mainstream bias hurts niche-genre listeners",
        (
            "too mainstream",
            "only mainstream",
            "always mainstream",
            "top 40",
            "no indie",
            "no jazz",
            "no classical",
            "no underground",
            "regional music",
            "regional artists",
            "niche genre",
        ),
    ),
    GroupRule(
        "Ads break the discovery flow on free tier",
        (
            "ads interrupt",
            "ads disrupt",
            "ads break",
            "ads while exploring",
            "ads during discovery",
            "free tier ads",
            "less interruptive free",
            "fewer ads",
            "no ads",
        ),
    ),
)


_REPETITION_CAUSE_RULES: tuple[GroupRule, ...] = (
    GroupRule(
        "Shuffle replays a small pool of tracks",
        (
            "shuffle plays the same",
            "shuffle is broken",
            "shuffle not random",
            "shuffle keeps",
            "shuffle repeat",
            "biased shuffle",
            "smarter shuffle",
            "better shuffle",
            "shuffle controls",
            "true shuffle",
            "shuffle playlist without repetition",
            "preventing repetitive listening",
            "shuffle same",
        ),
    ),
    GroupRule(
        "Autoplay/Radio cycles the same artists",
        (
            "autoplay same",
            "autoplay repetitive",
            "auto play same",
            "radio same",
            "radio repeat",
            "radio loop",
            "smarter autoplay",
            "autoplay novelty",
            "autoplay diversity",
        ),
    ),
    GroupRule(
        "Recommendation engine keeps surfacing favorites",
        (
            "recommend the same",
            "recommends the same",
            "suggesting the same",
            "playing favorites",
            "always playing the same",
            "keeps playing the same",
            "stuck on favorites",
            "already heard",
        ),
    ),
    GroupRule(
        "Discover Weekly recycles known tracks",
        (
            "discover weekly same",
            "discover weekly repeats",
            "discover weekly already saved",
            "discover weekly already liked",
            "avoid repetitive songs in discover weekly",
            "discover weekly familiar",
        ),
    ),
    GroupRule(
        "Single play permanently skews future suggestions",
        (
            "one play ruined",
            "single play",
            "accidentally played",
            "listened once",
            "one song ruined",
            "skew the algorithm",
        ),
    ),
    GroupRule(
        "Library / queue keeps looping back",
        (
            "queue loops",
            "library loops",
            "loop back",
            "over and over",
            "stuck in loop",
            "repeat playlist",
            "playlist loops",
        ),
    ),
    GroupRule(
        "Algorithm interprets repeat plays as strong preference",
        (
            "engagement loop",
            "reinforces favorites",
            "reinforcement loop",
            "amplifies past listening",
            "past plays bias",
            "listening history bias",
        ),
    ),
)


_DISCOVERY_FRUSTRATION_RULES: tuple[GroupRule, ...] = (
    GroupRule(
        "Recommendations feel stale and repetitive",
        (
            "stale recommend",
            "stale playlist",
            "stale mix",
            "stale radio",
            "tired playlist",
            "repetitive recommend",
            "boring playlist",
            "same old recommend",
            "fresher recommendation",
            "more diverse recommendations",
            "diverse recommendations",
        ),
    ),
    GroupRule(
        "Hard to escape past listening history",
        (
            "stuck in my history",
            "stuck in my profile",
            "trapped in profile",
            "locked into",
            "tied to history",
            "escape my profile",
            "escape my history",
            "outside my profile",
            "outside my taste",
        ),
    ),
    GroupRule(
        "Algorithm doesn't understand my taste",
        (
            "doesn't understand me",
            "doesn't understand my taste",
            "doesn't get me",
            "doesn't know what i like",
            "doesn't know me",
            "doesn't know my taste",
            "doesn't match my taste",
            "doesn't get my taste",
            "wrong taste",
            "miss the mark",
        ),
    ),
    GroupRule(
        "Discover Weekly disappoints over time",
        (
            "discover weekly used to",
            "discover weekly worse",
            "discover weekly disappointing",
            "discover weekly fell off",
            "discover weekly stopped working",
            "discover weekly is bad",
        ),
    ),
    GroupRule(
        "Ads disrupt active music exploration",
        (
            "ad in the middle",
            "ads interrupt",
            "ads disrupt",
            "ads break my",
            "ad break",
            "ads while listening",
            "ads when exploring",
            "fewer ads",
            "less interruptive free",
        ),
    ),
    GroupRule(
        "Skipping songs doesn't seem to teach the algorithm",
        (
            "skip but still",
            "skipped but it keeps",
            "skipping doesn't",
            "skipping does not",
            "still recommends after skip",
            "still plays after skip",
        ),
    ),
    GroupRule(
        "Wanted curator/social/human picks but only get algorithmic ones",
        (
            "wish for curator",
            "human curator",
            "editor picks",
            "friend recommendations",
            "social discovery",
            "community picks",
            "expert recommendations",
            "miss human curation",
            "more human artists",
        ),
    ),
)


_DISCOVERY_UNMET_NEED_RULES: tuple[GroupRule, ...] = (
    GroupRule(
        "More diverse recommendations",
        (
            "more diverse recommendations",
            "diverse recommendations",
            "more diverse",
            "wider variety",
            "broader recommendations",
            "less repetitive",
            "less familiar",
            "more variety",
        ),
    ),
    GroupRule(
        "Better personalization that learns from feedback",
        (
            "better personalization",
            "smarter personalization",
            "deeper personalization",
            "true personalization",
            "learn from me",
            "adapt to me",
            "understand my taste",
            "understands my taste",
            "learn my taste",
        ),
    ),
    GroupRule(
        "Dedicated discovery surfaces beyond Discover Weekly",
        (
            "dedicated discovery",
            "explore tab",
            "explore mode",
            "explore section",
            "exploration space",
            "exploration tab",
            "new discovery surface",
            "stronger curated discovery",
            "curated discovery playlists",
        ),
    ),
    GroupRule(
        "User control over algorithmic intensity / novelty",
        (
            "more control over recommend",
            "more control over the algorithm",
            "control the algorithm",
            "novelty slider",
            "discovery slider",
            "discovery intensity",
            "tune the algorithm",
            "algorithm controls",
        ),
    ),
    GroupRule(
        "Smarter shuffle and autoplay",
        (
            "smarter shuffle",
            "better shuffle",
            "true shuffle",
            "proper shuffle",
            "shuffle controls",
            "smarter autoplay",
            "better autoplay",
            "autoplay novelty",
        ),
    ),
    GroupRule(
        "Curator- or human-driven discovery",
        (
            "curator playlist",
            "human curator",
            "editorial playlist",
            "expert playlist",
            "curated discovery",
            "guided music discovery",
        ),
    ),
    GroupRule(
        "Social and friend-based discovery",
        (
            "friend discovery",
            "social discovery",
            "friend recommendations",
            "community playlist",
            "richer social listening",
            "sharing features",
            "friend activity",
        ),
    ),
    GroupRule(
        "Mood and context-aware recommendations",
        (
            "mood-aware",
            "mood aware",
            "mood-based",
            "context aware",
            "activity based",
            "workout playlist",
            "study mode",
            "focus mode",
            "sleep mode",
        ),
    ),
    GroupRule(
        "Fresher and more accurate recommendations",
        (
            "fresher and more accurate",
            "fresher recommendation",
            "more accurate recommendation",
            "fresh music",
            "new music feed",
            "fresh artist",
        ),
    ),
    GroupRule(
        "Easier music discovery (general)",
        (
            "easier music discovery",
            "easier to discover",
            "easier discovery",
            "simpler discovery",
            "better discovery",
        ),
    ),
)


def _matches_any(text: str, keywords: Iterable[str]) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in keywords)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _percent(n: int, denom: int) -> str:
    if not denom:
        return ""
    return f"{round(100.0 * n / denom, 1)}%"


def _row_text(row: pd.Series) -> str:
    parts: list[str] = []
    # Order matters: unmet_need first because it's the canonical inferred goal.
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
        if text and text.lower() not in {"none", "nan", "null", "n/a"}:
            parts.append(text)
    return " ".join(parts)


def _example_from_row(row: pd.Series) -> str:
    """Return a short, paraphrased example — prefer unmet_need (already paraphrased)."""
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
        if text and text.lower() not in {"none", "nan", "null", "n/a"}:
            return text[:160]
    return ""


def _group_dataframe(
    df: pd.DataFrame,
    rules: Iterable[GroupRule],
    *,
    corpus_total: int,
    pool_total: int,
    other_label: str = "Other discovery-related signal",
) -> list[dict[str, Any]]:
    rule_list = list(rules)
    if df.empty or not rule_list:
        return []

    text_blobs = df.apply(_row_text, axis=1).str.lower()
    examples_pool = df.apply(_example_from_row, axis=1)

    groups: list[dict[str, Any]] = []
    seen_rows: set[int] = set()

    for rule in rule_list:
        # Build OR mask across keywords (substring match — case-insensitive).
        mask = pd.Series(False, index=df.index)
        for kw in rule.keywords:
            if not kw:
                continue
            mask = mask | text_blobs.str.contains(kw.lower(), regex=False, na=False)
        if not mask.any():
            continue
        matched_idx = list(df.index[mask])
        count = len(matched_idx)
        slice_df = df.loc[matched_idx]
        source_counts = source_counts_from_frame(slice_df)
        examples_seen: list[str] = []
        for idx in matched_idx:
            seen_rows.add(int(idx))
            example = examples_pool.loc[idx]
            if example and example not in examples_seen:
                examples_seen.append(example)
            if len(examples_seen) >= 3:
                break
        groups.append({
            "label": rule.label,
            "count": int(count),
            "share_of_corpus": _percent(count, corpus_total),
            "share_of_pool": _percent(count, pool_total) if pool_total else "",
            "source_counts": source_counts,
            "examples": examples_seen,
        })

    unmatched = pool_total - len(seen_rows)
    if unmatched > 0:
        groups.append({
            "label": other_label,
            "count": int(unmatched),
            "share_of_corpus": _percent(unmatched, corpus_total),
            "share_of_pool": _percent(unmatched, pool_total) if pool_total else "",
            "examples": [],
        })

    groups.sort(key=lambda g: g["count"], reverse=True)
    return groups


def _discovery_pool(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "is_discovery_related" not in df.columns:
        return df.head(0)
    return df[df["is_discovery_related"] == True].copy()  # noqa: E712


def _repetition_pool(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.head(0)
    if "is_repetition_related" not in df.columns:
        return df.head(0)
    return df[df["is_repetition_related"] == True].copy()  # noqa: E712


def _negative_pool(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "sentiment" not in df.columns:
        return df
    sent = df["sentiment"].astype(str).str.lower()
    return df[sent.isin({"negative", "mixed"})].copy()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _build_payload(df: pd.DataFrame) -> dict[str, Any]:
    total = int(len(df))
    discovery_df = _discovery_pool(df)
    repetition_df = _repetition_pool(df)
    discovery_negative_df = _negative_pool(discovery_df)

    payload: dict[str, Any] = {
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "totals": {
            "total_reviews": total,
            "discovery_related": int(len(discovery_df)),
            "discovery_related_share": _percent(len(discovery_df), total),
            "repetition_related": int(len(repetition_df)),
            "repetition_related_share": _percent(len(repetition_df), total),
        },
        "discovery_struggles": {
            "description": "Why users struggle to discover new music",
            "pool_size": int(len(discovery_df)),
            "pool_share_of_corpus": _percent(len(discovery_df), total),
            "groups": _group_dataframe(
                discovery_df, _DISCOVERY_STRUGGLE_RULES,
                corpus_total=total, pool_total=len(discovery_df),
                other_label="Other discovery struggle (uncategorised)",
            ),
        },
        "repetition_causes": {
            "description": "What causes repetitive listening behaviour",
            "pool_size": int(len(repetition_df)),
            "pool_share_of_corpus": _percent(len(repetition_df), total),
            "groups": _group_dataframe(
                repetition_df, _REPETITION_CAUSE_RULES,
                corpus_total=total, pool_total=len(repetition_df),
                other_label="Other repetition signal (uncategorised)",
            ),
        },
        "discovery_frustrations": {
            "description": "Concrete frustrations expressed about music discovery",
            "pool_size": int(len(discovery_negative_df)),
            "pool_share_of_corpus": _percent(len(discovery_negative_df), total),
            "groups": _group_dataframe(
                discovery_negative_df, _DISCOVERY_FRUSTRATION_RULES,
                corpus_total=total, pool_total=len(discovery_negative_df),
                other_label="Other discovery frustration (uncategorised)",
            ),
        },
        "discovery_unmet_needs": {
            "description": "What users wish discovery would deliver",
            "pool_size": int(len(discovery_df)),
            "pool_share_of_corpus": _percent(len(discovery_df), total),
            "groups": _group_dataframe(
                discovery_df, _DISCOVERY_UNMET_NEED_RULES,
                corpus_total=total, pool_total=len(discovery_df),
                other_label="Other discovery unmet need (uncategorised)",
            ),
        },
    }
    return payload


@lru_cache(maxsize=1)
def compute_discovery_insights() -> dict[str, Any]:
    df = load_insights_df()
    return _build_payload(df)


def reset_cache() -> None:
    compute_discovery_insights.cache_clear()


__all__ = ["compute_discovery_insights", "reset_cache"]


if __name__ == "__main__":  # pragma: no cover - manual smoke
    import json
    print(json.dumps(compute_discovery_insights(), indent=2, default=str)[:4000])
