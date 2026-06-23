"""Load Phase-2 insights into a clustering-ready in-memory table.

Responsibilities:
- Read `data/processed/insights.csv`
- Deduplicate by `review_id` (Phase 2's CSV can have duplicate rows when the
  LLM echoed an id across batches; we keep the first one)
- Optionally filter to discovery-related insights only
- Build the `text_to_embed` field (`verbatim_quote` + `unmet_need`), which is
  the densest signal we have per review and what BERTopic will cluster
- Drop empty / near-empty docs that would create degenerate clusters
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import pandas as pd
from loguru import logger

from .config import settings


_MIN_TEXT_CHARS = 8


def _coerce_str(x) -> str:
    if x is None:
        return ""
    s = str(x).strip()
    if s.lower() in {"nan", "none"}:
        return ""
    return s


def _coerce_bool(x) -> bool:
    if isinstance(x, bool):
        return x
    s = str(x).strip().lower()
    return s in {"true", "1", "yes"}


def build_text_to_embed(verbatim_quote: str, unmet_need: str) -> str:
    """Compose the string we hand to the embedding model.

    Phase 2 already distilled each review into:
      - a verbatim quote (what the user actually said), and
      - an unmet_need paraphrase (what they want).

    Concatenating both gives the embedder both the surface form AND the
    intent — much cleaner than re-embedding raw reviews full of noise.
    """
    parts: List[str] = []
    q = verbatim_quote.strip()
    if q:
        parts.append(q)

    n = unmet_need.strip()
    if n and n.lower() != "none":
        parts.append(f"Need: {n}")

    return " :: ".join(parts).strip()


def load_insights(
    csv_path: Optional[Path] = None,
    discovery_only: Optional[bool] = None,
) -> pd.DataFrame:
    """Load the Phase-2 insights CSV, dedupe, filter, and add `text_to_embed`."""
    path = Path(csv_path) if csv_path else settings.insights_csv_path
    if not path.exists():
        raise FileNotFoundError(
            f"Phase 2 insights CSV not found at {path}. Run `python run_phase2.py` first."
        )

    df = pd.read_csv(path)
    logger.info("[loader] loaded {n} rows from {p}", n=len(df), p=path)

    df["review_id"] = df["review_id"].map(_coerce_str)
    df = df[df["review_id"] != ""].copy()

    before = len(df)
    df = df.drop_duplicates(subset=["review_id"], keep="first").reset_index(drop=True)
    dupes = before - len(df)
    if dupes:
        logger.info("[loader] dropped {d} duplicate review_id rows", d=dupes)

    for col in ("verbatim_quote", "unmet_need", "source", "pain_category", "sentiment", "segment"):
        if col in df.columns:
            df[col] = df[col].map(_coerce_str)
        else:
            df[col] = ""

    if "discovery_related" in df.columns:
        df["discovery_related"] = df["discovery_related"].map(_coerce_bool)
    else:
        df["discovery_related"] = False

    want_discovery_only = (
        discovery_only if discovery_only is not None else settings.cluster_discovery_only
    )
    if want_discovery_only:
        before = len(df)
        df = df[df["discovery_related"]].reset_index(drop=True)
        logger.info(
            "[loader] discovery-only filter: kept {k}/{b}",
            k=len(df), b=before,
        )

    df["text_to_embed"] = [
        build_text_to_embed(q, n)
        for q, n in zip(df["verbatim_quote"], df["unmet_need"])
    ]

    before = len(df)
    df = df[df["text_to_embed"].str.len() >= _MIN_TEXT_CHARS].reset_index(drop=True)
    dropped = before - len(df)
    if dropped:
        logger.info("[loader] dropped {d} rows with empty/near-empty text", d=dropped)

    logger.info(
        "[loader] ready for clustering: {n} docs (avg len={a:.0f} chars)",
        n=len(df),
        a=df["text_to_embed"].str.len().mean() if len(df) else 0,
    )
    return df
