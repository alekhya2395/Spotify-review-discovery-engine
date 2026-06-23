"""Load and prepare insights data for synthesis."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from loguru import logger


def load_insights(csv_path: Path) -> pd.DataFrame:
    """Read insights.csv and return a clean DataFrame."""
    logger.info("Loading insights from {}", csv_path)
    df = pd.read_csv(csv_path)
    logger.info("Loaded {} insights across {} sources", len(df), df["source"].nunique())

    df["discovery_related"] = df["discovery_related"].astype(str).str.lower().map(
        {"true": True, "false": False}
    )
    df["confidence"] = pd.to_numeric(df["confidence"], errors="coerce")
    return df
