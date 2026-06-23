"""Loads processed insights, themes, and report from bundled data files.

On Railway, the `data/` folder is committed to the repo and shipped with the app.
Files are read once at startup and cached in memory.
"""

import json
import os
from functools import lru_cache
from pathlib import Path

import pandas as pd

DATA_DIR = Path(os.getenv("DATA_DIR", Path(__file__).parent / "data")).resolve()


def _latest(pattern: str) -> Path | None:
    files = sorted(DATA_DIR.glob(pattern))
    return files[-1] if files else None


@lru_cache(maxsize=1)
def load_insights_df() -> pd.DataFrame:
    """Load the most recent processed insights CSV into a DataFrame."""
    path = _latest("insights_*.csv")
    if not path:
        return pd.DataFrame()
    df = pd.read_csv(path)
    for col in ("is_discovery_related", "is_repetition_related"):
        if col in df.columns:
            df[col] = df[col].fillna(False).astype(bool)
    return df


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
    """Quick stats for diagnostics."""
    df = load_insights_df()
    themes = load_themes()
    return {
        "data_dir": str(DATA_DIR),
        "insights_rows": len(df),
        "themes_count": len(themes.get("themes", {}).get("themes", [])) if themes else 0,
        "report_chars": len(load_report_md()),
    }
