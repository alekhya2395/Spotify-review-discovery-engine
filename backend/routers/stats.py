"""High-level summary metrics for the dashboard hero section."""

import pandas as pd
from fastapi import APIRouter

from data_loader import load_insights_df, load_themes

router = APIRouter()


@router.get("/stats")
def stats() -> dict:
    df = load_insights_df()
    themes = load_themes()

    if df.empty:
        return {
            "total_items": 0,
            "discovery_related": 0,
            "repetition_related": 0,
            "avg_sentiment": 0.0,
            "avg_sentiment_score": 0.0,
            "top_pain_category": "",
            "themes_count": 0,
            "sources": {},
            "pain_categories": {},
            "sentiment_distribution": {},
        }

    pain = (
        df["pain_category"]
        .dropna()
        .astype(str)
        .replace("", pd.NA)
        .dropna()
    )
    pain = pain[pain.str.lower() != "none"]
    pain_counts = pain.value_counts().head(10).to_dict() if not pain.empty else {}

    if "sentiment" in df.columns:
        sent = df["sentiment"].fillna("neutral").astype(str).str.lower()
        sentiment_distribution = sent.value_counts().to_dict()
    else:
        sentiment_distribution = {}

    avg_intensity = float(df["sentiment_intensity"].dropna().mean() or 3.0)

    return {
        "total_items": int(len(df)),
        "discovery_related": int(df["is_discovery_related"].sum()),
        "repetition_related": int(df["is_repetition_related"].sum()),
        "avg_sentiment": round((avg_intensity - 3.0) / 2.0, 2),
        "avg_sentiment_score": round(avg_intensity, 2),
        "top_pain_category": next(iter(pain_counts), ""),
        "themes_count": len(themes.get("themes", {}).get("themes", [])) if themes else 0,
        "sources": df["source"].value_counts().to_dict(),
        "pain_categories": pain_counts,
        "sentiment_distribution": sentiment_distribution,
    }
