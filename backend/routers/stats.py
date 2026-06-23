"""High-level summary metrics for the dashboard hero section."""

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
            "themes_count": 0,
            "sources": {},
            "pain_categories": {},
        }

    return {
        "total_items": int(len(df)),
        "discovery_related": int(df["is_discovery_related"].sum()),
        "repetition_related": int(df["is_repetition_related"].sum()),
        "avg_sentiment": round(float(df["sentiment_intensity"].dropna().mean() or 0), 2),
        "themes_count": len(themes.get("themes", {}).get("themes", [])) if themes else 0,
        "sources": df["source"].value_counts().to_dict(),
        "pain_categories": df["pain_category"].dropna().value_counts().head(10).to_dict(),
    }
