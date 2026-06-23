"""Load all upstream artifacts for Phase-5 indexing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional, Set

import numpy as np
import pandas as pd
from loguru import logger

from src.phase3_clustering.storage import LIST_DELIM

from .config import settings


def _split_list(val) -> list:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return []
    s = str(val).strip()
    if not s:
        return []
    return [x.strip() for x in s.split(LIST_DELIM) if x.strip()]


def load_raw_reviews() -> pd.DataFrame:
    """Load unique raw reviews from the data lake JSONL files."""
    root = settings.raw_data_dir
    if not root.exists():
        logger.warning("[loaders] raw dir missing: {p}", p=root)
        return pd.DataFrame()

    seen: Set[str] = set()
    rows = []
    for path in sorted(root.rglob("*.jsonl")):
        if path.name == "manifest.jsonl":
            continue
        try:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    rid = rec.get("review_id")
                    if not rid or rid in seen or not rec.get("text"):
                        continue
                    seen.add(rid)
                    rows.append(
                        {
                            "review_id": rid,
                            "source": rec.get("source"),
                            "source_region": rec.get("source_region"),
                            "text": rec.get("text"),
                            "title": rec.get("title"),
                            "rating": rec.get("rating"),
                            "lang": rec.get("lang"),
                            "author": rec.get("author"),
                            "created_at": rec.get("created_at"),
                            "url": rec.get("url"),
                            "collected_at": rec.get("collected_at"),
                        }
                    )
        except OSError as exc:
            logger.debug("[loaders] skip {p}: {e}", p=path, e=exc)

    df = pd.DataFrame(rows)
    logger.info("[loaders] raw reviews: {n}", n=len(df))
    return df


def load_insights_deduped() -> pd.DataFrame:
    path = settings.processed_data_dir / settings.insights_csv
    if not path.exists():
        raise FileNotFoundError(f"insights.csv not found at {path}. Run Phase 2 first.")
    df = pd.read_csv(path)
    before = len(df)
    df = df.drop_duplicates(subset=["review_id"], keep="first").reset_index(drop=True)
    if before != len(df):
        logger.info("[loaders] insights deduped {b} -> {a}", b=before, a=len(df))
    return df


def load_insights_with_topics() -> pd.DataFrame:
    path = settings.processed_data_dir / settings.insights_with_topics_csv
    if not path.exists():
        raise FileNotFoundError(
            f"insights_with_topics.csv not found at {path}. Run Phase 3 first."
        )
    return pd.read_csv(path)


def load_topics() -> pd.DataFrame:
    path = settings.processed_data_dir / settings.topics_csv
    if not path.exists():
        raise FileNotFoundError(f"topics.csv not found at {path}. Run Phase 3 first.")
    df = pd.read_csv(path)
    for col in ("keywords", "representative_quotes", "representative_review_ids", "top_sources"):
        if col in df.columns:
            df[col] = df[col].map(_split_list)
    return df


def load_insight_cards() -> pd.DataFrame:
    path = settings.processed_data_dir / settings.insight_cards_csv
    if not path.exists():
        raise FileNotFoundError(
            f"insight_cards.csv not found at {path}. Run Phase 4 first."
        )
    df = pd.read_csv(path)
    for col in (
        "affected_segments",
        "top_unmet_needs",
        "evidence_quotes",
        "evidence_review_ids",
        "top_sources",
    ):
        if col in df.columns:
            df[col] = df[col].map(_split_list)
    return df


def load_embeddings() -> tuple[np.ndarray, pd.DataFrame]:
    """Return (embedding matrix, index dataframe with review_id per row)."""
    npy = settings.embeddings_npy_path
    idx_csv = settings.embedding_index_csv_path
    if not npy.exists() or not idx_csv.exists():
        raise FileNotFoundError(
            "embeddings.npy / embedding_index.csv not found. Run Phase 3 first."
        )
    emb = np.load(npy)
    idx = pd.read_csv(idx_csv)
    if emb.shape[0] != len(idx):
        raise ValueError(
            f"Embedding rows ({emb.shape[0]}) != index rows ({len(idx)})"
        )
    logger.info("[loaders] embeddings: {n} x {d}", n=emb.shape[0], d=emb.shape[1])
    return emb, idx


def build_enriched_reviews(
    raw_df: pd.DataFrame,
    enriched_df: pd.DataFrame,
) -> pd.DataFrame:
    """Join raw reviews with Phase-2/3 enriched fields."""
    if raw_df.empty:
        return enriched_df.copy()

    keep_raw = [
        c
        for c in ("review_id", "text", "title", "rating", "created_at", "url", "source_region", "lang")
        if c in raw_df.columns
    ]
    merged = enriched_df.merge(raw_df[keep_raw], on="review_id", how="left", suffixes=("", "_raw"))

    if "text_raw" in merged.columns:
        merged["text"] = merged["text"].fillna(merged["text_raw"])
        merged = merged.drop(columns=["text_raw"])
    if "source" not in merged.columns and "source_raw" in merged.columns:
        merged["source"] = merged["source_raw"]

    return merged
