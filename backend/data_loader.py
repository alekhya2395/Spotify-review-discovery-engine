"""Loads processed insights, themes, and report from bundled data files."""

import json
import os
import sys
from functools import lru_cache
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent))

from unmet_need_inference import fill_unmet_needs  # noqa: E402

DATA_DIR = Path(os.getenv("DATA_DIR", Path(__file__).parent / "data")).resolve()

SENTIMENT_SCORE = {"negative": 2, "mixed": 3, "neutral": 3, "positive": 4}


def _latest(pattern: str) -> Path | None:
    files = sorted(DATA_DIR.glob(pattern))
    return files[-1] if files else None


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.drop_duplicates(subset=["review_id"], keep="first").copy()

    if "is_discovery_related" not in out.columns and "discovery_related" in out.columns:
        out["is_discovery_related"] = (
            out["discovery_related"].astype(str).str.lower().map({"true": True, "false": False})
        )

    if "is_repetition_related" not in out.columns:
        text = out.get("unmet_need", pd.Series(dtype=str)).astype(str)
        quotes = out.get("verbatim_quote", pd.Series(dtype=str)).astype(str)
        out["is_repetition_related"] = (
            (out.get("pain_category") == "listening_behavior")
            | text.str.contains("repetit|shuffle|same song|loop", case=False, na=False)
            | quotes.str.contains("repetit|shuffle|same song|loop", case=False, na=False)
        )

    if "sentiment_intensity" not in out.columns and "sentiment" in out.columns:
        out["sentiment_intensity"] = out["sentiment"].map(SENTIMENT_SCORE).fillna(3)

    if "listening_style" not in out.columns and "segment" in out.columns:
        out["listening_style"] = out["segment"]

    for col in ("is_discovery_related", "is_repetition_related"):
        if col in out.columns:
            out[col] = out[col].fillna(False).astype(bool)

    out = fill_unmet_needs(out)

    return out


@lru_cache(maxsize=1)
def load_insights_df() -> pd.DataFrame:
    path = _latest("insights_*.csv")
    if not path:
        return pd.DataFrame()
    return _normalize(pd.read_csv(path))


@lru_cache(maxsize=1)
def load_themes() -> dict:
    path = _latest("themes_*.json")
    if not path:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_report_md() -> str:
    path = _latest("discovery_insights_report_*.md")
    if not path:
        return ""
    return path.read_text(encoding="utf-8")


def data_summary() -> dict:
    df = load_insights_df()
    themes = load_themes()
    return {
        "data_dir": str(DATA_DIR),
        "insights_rows": len(df),
        "themes_count": len(themes.get("themes", {}).get("themes", [])) if themes else 0,
        "report_chars": len(load_report_md()),
    }
