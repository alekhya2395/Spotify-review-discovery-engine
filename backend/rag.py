"""Retrieve review context for grounded chat answers."""

from __future__ import annotations

import json
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data_loader import load_insights_df, load_themes  # noqa: E402

TEXT_COLS = (
    "verbatim_quote",
    "specific_pain",
    "unmet_need",
    "user_suggested_fix",
    "pain_category",
    "listening_style",
    "source",
)

_SEARCH_STOPWORDS = frozenset({
    "what", "when", "where", "which", "who", "why", "how", "does", "do", "did",
    "are", "is", "was", "were", "the", "and", "for", "with", "about", "from",
    "that", "this", "those", "these", "have", "has", "had", "can", "could",
    "would", "should", "will", "been", "being", "most", "more", "some", "such",
    "than", "then", "also", "just", "only", "very", "much", "many", "often",
    "users", "user", "spotify", "music", "tell", "explain", "describe", "list",
    "show", "common", "main", "top", "biggest", "issues", "issue", "problem",
})

# Strip internal review IDs from model output (e.g. app_store:14207861013).
REVIEW_ID_PATTERN = re.compile(
    r"(?:\b(?:review[_\s-]?id[:\s]*)?)?"
    r"(?:app_store|play_store|reddit|social_media|community_forum):[^\s\]\),.;\"']+",
    re.IGNORECASE,
)
MASTODON_ID = re.compile(r"mastodon_https?://[^\s\]\),.;\"']+", re.IGNORECASE)
REVIEW_ID_LABEL = re.compile(r"\breview[_\s-]?id[:\s]+[^\s\]\),.;\"']+", re.IGNORECASE)


def sanitize_answer(text: str) -> str:
    """Remove internal review reference codes from chat answers."""
    if not text:
        return text
    cleaned = REVIEW_ID_PATTERN.sub("", text)
    cleaned = MASTODON_ID.sub("", cleaned)
    cleaned = REVIEW_ID_LABEL.sub("", cleaned)
    cleaned = re.sub(r"\(\s*\)", "", cleaned)
    cleaned = re.sub(r"[^\S\n]{2,}", " ", cleaned)  # collapse spaces/tabs only, keep newlines
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _text_search(df: pd.DataFrame, question: str, k: int = 20) -> pd.DataFrame:
    if df.empty or not question.strip():
        return df.head(0)

    needle = question.strip().lower()
    tokens = [t for t in needle.replace("?", " ").split() if len(t) > 2]
    tokens = [t for t in tokens if t not in _SEARCH_STOPWORDS]
    if not tokens:
        tokens = [t for t in needle.replace("?", " ").split() if len(t) > 2]

    cols = [c for c in TEXT_COLS if c in df.columns]
    if not cols:
        return df.head(0)

    scores = pd.Series(0, index=df.index, dtype=int)
    for col in cols:
        series = df[col].fillna("").astype(str).str.lower()
        for token in tokens:
            scores += series.str.contains(token, regex=False).astype(int)

    # Boost rows that match the question's dominant topic
    q = needle
    if any(w in q for w in ("struggle", "difficult", "hard")) and "discover" in q:
        if "pain_category" in df.columns:
            scores += df["pain_category"].fillna("").astype(str).str.lower().isin(
                {"discovery", "recommendation_quality", "algorithm_repetition"}
            ).astype(int) * 4
        if "is_discovery_related" in df.columns:
            scores += df["is_discovery_related"].fillna(False).astype(int) * 2
    elif any(w in q for w in ("price", "premium", "subscription", "ads", "free tier")):
        if "pain_category" in df.columns:
            scores += df["pain_category"].fillna("").astype(str).str.lower().isin(
                {"pricing", "pricing_complaints", "ads"}
            ).astype(int) * 4
    elif any(w in q for w in ("bluetooth", "audio", "sound", "quality")):
        if "pain_category" in df.columns:
            scores += df["pain_category"].fillna("").astype(str).str.lower().eq("audio_quality").astype(int) * 4
    elif any(w in q for w in ("podcast", "audiobook")):
        if "pain_category" in df.columns:
            scores += df["pain_category"].fillna("").astype(str).str.lower().isin(
                {"content_availability", "catalog_gaps"}
            ).astype(int) * 3
        for col in cols:
            series = df[col].fillna("").astype(str).str.lower()
            scores += series.str.contains("podcast", regex=False).astype(int) * 3

    ranked = df.loc[scores > 0].copy()
    if ranked.empty:
        if "is_discovery_related" in df.columns:
            ranked = df[df["is_discovery_related"] == True].copy()  # noqa: E712
        if ranked.empty:
            ranked = df.copy()

    ranked["_score"] = scores.loc[ranked.index]
    ranked = ranked.sort_values("_score", ascending=False).head(k)
    return ranked.drop(columns=["_score"], errors="ignore")


@lru_cache(maxsize=1)
def _query_engine():
    try:
        from src.phase5_storage.query import QueryEngine

        return QueryEngine()
    except Exception:
        return None


def _semantic_search(question: str, k: int = 12) -> list[dict[str, Any]]:
    engine = _query_engine()
    if engine is None:
        return []
    try:
        return engine.semantic_search(question, k=k)[:k]
    except Exception:
        return []


def _format_source(source: str | None) -> str | None:
    if not source:
        return None
    labels = {
        "app_store": "App Store",
        "play_store": "Google Play",
        "reddit": "Reddit",
        "social_media": "Social Media",
        "community_forum": "Community Forum",
    }
    return labels.get(str(source).lower(), str(source).replace("_", " ").title())


def _insight_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Export review excerpts for the LLM — no internal review_id fields."""
    records: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        records.append(
            {
                "source": _format_source(row.get("source")),
                "sentiment": row.get("sentiment"),
                "pain_category": row.get("pain_category"),
                "segment": row.get("listening_style"),
                "quote": row.get("verbatim_quote") or row.get("specific_pain"),
                "unmet_need": row.get("unmet_need"),
            }
        )
    return records


def _stats_snapshot(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {"total_reviews": 0}
    out: dict[str, Any] = {"total_reviews": int(len(df))}
    if "is_discovery_related" in df.columns:
        out["discovery_related"] = int(df["is_discovery_related"].sum())
    if "pain_category" in df.columns:
        out["top_pain_categories"] = df["pain_category"].value_counts().head(8).to_dict()
    if "source" in df.columns:
        out["sources"] = {
            _format_source(k) or k: int(v) for k, v in df["source"].value_counts().items()
        }
    if "sentiment" in df.columns:
        out["sentiments"] = df["sentiment"].value_counts().to_dict()
    if "listening_style" in df.columns:
        out["segments"] = df["listening_style"].value_counts().head(12).to_dict()
    if "unmet_need" in df.columns:
        needs = df["unmet_need"].dropna().astype(str)
        needs = needs[~needs.str.lower().isin({"none", "nan", ""})]
        if not needs.empty:
            out["top_unmet_needs"] = needs.value_counts().head(12).to_dict()
    if "listening_style" in df.columns and "is_discovery_related" in df.columns:
        seg_disc = (
            df[df["is_discovery_related"] == True]  # noqa: E712
            .groupby("listening_style")
            .size()
            .sort_values(ascending=False)
            .head(10)
        )
        out["discovery_by_segment"] = {str(k): int(v) for k, v in seg_disc.items()}
    return out


def _theme_records(themes: list[dict[str, Any]], limit: int = 15) -> list[dict[str, Any]]:
    slim = []
    for t in themes[:limit]:
        slim.append(
            {
                "theme_name": t.get("theme_name"),
                "summary": t.get("one_line_summary"),
                "dominant_segment": t.get("dominant_segment"),
                "severity": t.get("severity"),
                "sample_quotes": (t.get("representative_quotes") or [])[:3],
                "what_users_want": t.get("what_users_want_instead"),
            }
        )
    return slim


def build_review_context(question: str) -> tuple[dict[str, Any], str, dict[str, Any]]:
    """Build grounding payload for chat. Returns (payload dict, JSON text, meta)."""
    df = load_insights_df()
    themes_payload = load_themes()
    theme_list = themes_payload.get("themes", {}).get("themes", []) if themes_payload else []

    keyword_hits = _text_search(df, question, k=20)

    # Skip semantic search in the API chat path — it loads a large embedder and can timeout.
    semantic_hits: list[dict[str, Any]] = []

    semantic_ids = {h.get("review_id") for h in semantic_hits if h.get("review_id")}
    extra_rows = pd.DataFrame()
    if semantic_ids and "review_id" in df.columns:
        extra_rows = df[df["review_id"].isin(semantic_ids)].head(10)

    combined = pd.concat([keyword_hits, extra_rows], ignore_index=True)
    if "review_id" in combined.columns:
        combined = combined.drop_duplicates(subset=["review_id"], keep="first")

    matched_reviews = _insight_records(combined.head(22))
    semantic_excerpts = []
    for hit in semantic_hits[:10]:
        detail = hit.get("detail") or hit.get("metadata") or {}
        semantic_excerpts.append(
            {
                "source": _format_source(detail.get("source") or hit.get("source")),
                "pain_category": detail.get("pain_category"),
                "topic": detail.get("topic_label"),
                "quote": detail.get("verbatim_quote") or hit.get("document"),
            }
        )

    payload: dict[str, Any] = {
        "dataset_stats": _stats_snapshot(df),
        "themes": _theme_records(theme_list, limit=12),
        "matched_reviews": matched_reviews,
        "semantic_matches": semantic_excerpts,
    }

    # Shrink payload until JSON fits — never slice raw JSON (that breaks parsing in fallback).
    while len(json.dumps(payload, ensure_ascii=False, default=str)) > 12000:
        if len(payload["matched_reviews"]) > 4:
            payload["matched_reviews"] = payload["matched_reviews"][:-3]
        elif len(payload["themes"]) > 3:
            payload["themes"] = payload["themes"][:-2]
        else:
            break

    text = json.dumps(payload, ensure_ascii=False, default=str)
    meta = {
        "keyword_matches": len(payload["matched_reviews"]),
        "semantic_matches": len(semantic_excerpts),
        "total_reviews": len(df),
    }
    return payload, text, meta
