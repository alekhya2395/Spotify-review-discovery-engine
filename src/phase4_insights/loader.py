"""Load Phase-3 outputs and optional review timestamps from the raw lake."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional, Set

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


def load_topics_and_insights(
    topics_path: Optional[Path] = None,
    insights_path: Optional[Path] = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load `topics.csv` and `insights_with_topics.csv`."""
    tpath = Path(topics_path) if topics_path else settings.topics_csv_path
    ipath = Path(insights_path) if insights_path else settings.insights_with_topics_csv_path

    if not tpath.exists():
        raise FileNotFoundError(
            f"topics.csv not found at {tpath}. Run `python run_phase3.py` first."
        )
    if not ipath.exists():
        raise FileNotFoundError(
            f"insights_with_topics.csv not found at {ipath}. Run `python run_phase3.py` first."
        )

    topics = pd.read_csv(tpath)
    insights = pd.read_csv(ipath)

    for col in ("keywords", "representative_quotes", "representative_review_ids", "top_sources"):
        if col in topics.columns:
            topics[col] = topics[col].map(_split_list)

    logger.info(
        "[loader] topics={t}  insights_with_topics={i}",
        t=len(topics),
        i=len(insights),
    )
    return topics, insights


def load_review_timestamps(review_ids: Optional[Set[str]] = None) -> Dict[str, pd.Timestamp]:
    """Build review_id -> created_at from raw JSONL (best-effort).

    Only reads files if RAW_DATA_DIR exists. Used for trend detection in Phase 4.
    """
    root = settings.raw_data_dir
    out: Dict[str, pd.Timestamp] = {}
    if not root.exists():
        logger.info("[loader] raw data dir missing — trend will be 'unknown'")
        return out

    want = review_ids or set()
    files = 0
    for path in sorted(root.rglob("*.jsonl")):
        if path.name == "manifest.jsonl":
            continue
        files += 1
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
                    if not rid:
                        continue
                    if want and rid not in want:
                        continue
                    ts = rec.get("created_at")
                    if ts:
                        try:
                            out[rid] = pd.to_datetime(ts, utc=True)
                        except (ValueError, TypeError):
                            pass
        except OSError as exc:
            logger.debug("[loader] skip {p}: {e}", p=path, e=exc)

    logger.info("[loader] timestamps for {n} reviews from {f} jsonl files", n=len(out), f=files)
    return out
