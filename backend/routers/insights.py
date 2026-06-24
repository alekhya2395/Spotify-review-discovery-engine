"""Filtered + paginated access to individual insights for the Review Explorer."""

from typing import Optional

from fastapi import APIRouter, Query

from data_loader import load_insights_df

router = APIRouter()


@router.get("/insights")
def list_insights(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    pain_category: Optional[str] = None,
    geography: Optional[str] = None,
    listening_style: Optional[str] = None,
    source: Optional[str] = None,
    discovery_only: bool = False,
    min_sentiment: Optional[int] = Query(None, ge=1, le=5),
    q: Optional[str] = Query(None, min_length=1, max_length=200),
    sentiment: Optional[str] = None,
) -> dict:
    df = load_insights_df()
    if df.empty:
        return {"items": [], "total": 0, "page": page, "page_size": page_size}

    view = df.copy()
    if discovery_only:
        view = view[view["is_discovery_related"] == True]  # noqa: E712
    if q:
        needle = q.strip().lower()
        text_cols = [c for c in ("verbatim_quote", "specific_pain", "unmet_need", "user_suggested_fix", "pain_category") if c in view.columns]
        if text_cols:
            mask = False
            for col in text_cols:
                mask = mask | view[col].fillna("").astype(str).str.lower().str.contains(needle, regex=False)
            view = view[mask]
    if sentiment and "sentiment" in view.columns:
        view = view[view["sentiment"].astype(str).str.lower() == sentiment.lower()]
    if pain_category:
        view = view[view["pain_category"] == pain_category]
    if geography:
        view = view[view["geography"] == geography]
    if listening_style:
        view = view[view["listening_style"] == listening_style]
    if source:
        view = view[view["source"] == source]
    if min_sentiment is not None:
        view = view[view["sentiment_intensity"] >= min_sentiment]

    view = view.sort_values("sentiment_intensity", ascending=False, na_position="last")
    total = len(view)
    start = (page - 1) * page_size
    end = start + page_size
    slice_df = view.iloc[start:end]

    cols = [
        "review_id", "source", "sentiment", "country", "rating", "pain_category",
        "specific_pain", "verbatim_quote", "sentiment_intensity",
        "geography", "language_preference", "listening_style", "unmet_need",
        "user_suggested_fix", "url",
    ]
    cols = [c for c in cols if c in slice_df.columns]

    items = slice_df[cols].where(slice_df[cols].notna(), None).to_dict(orient="records")

    return {
        "items": items,
        "total": int(total),
        "page": page,
        "page_size": page_size,
    }


@router.get("/insights/filters")
def filter_options() -> dict:
    """Returns distinct values for each filterable dimension."""
    df = load_insights_df()
    if df.empty:
        return {}

    def _distinct(col: str) -> list[str]:
        if col not in df.columns:
            return []
        return sorted([str(v) for v in df[col].dropna().unique() if str(v).strip() and str(v) != "nan"])

    return {
        "pain_categories": _distinct("pain_category"),
        "geographies": _distinct("geography"),
        "listening_styles": _distinct("listening_style"),
        "language_preferences": _distinct("language_preference"),
        "sources": _distinct("source"),
        "sentiments": _distinct("sentiment"),
    }
