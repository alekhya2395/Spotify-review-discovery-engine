"""Transform pipeline outputs into the bundled files the FastAPI backend expects.

Run from project root:
    python backend/prepare_data.py
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

try:
    from langdetect import DetectorFactory, detect

    DetectorFactory.seed = 0
    _HAS_LANGDETECT = True
except ImportError:
    _HAS_LANGDETECT = False

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "data"
STAMP = datetime.now(timezone.utc).strftime("%Y%m%d")

SENTIMENT_SCORE = {"positive": 4, "negative": 2, "neutral": 3, "mixed": 3}
SEVERITY_FROM_SENTIMENT = {"negative": 5, "neutral": 3, "positive": 2, "mixed": 3}


def _split_list(val) -> list[str]:
    if pd.isna(val) or not str(val).strip():
        return []
    return [x.strip() for x in str(val).split(" || ") if x.strip()]


def _load_lang_map() -> dict[str, str | None]:
    lang_map: dict[str, str | None] = {}
    for path in ROOT.glob("data/raw/**/*.jsonl"):
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
                    if rid:
                        lang_map[str(rid)] = rec.get("lang")
        except OSError:
            continue
    return lang_map


def _is_english(review_id: str, text: str | None, lang_map: dict[str, str | None]) -> bool:
    lang = lang_map.get(str(review_id))
    if lang:
        return str(lang).lower() == "en"

    quote = str(text or "").strip()
    if len(quote) < 15:
        return False
    if not _HAS_LANGDETECT:
        # Fallback: mostly ASCII Latin text when langdetect is unavailable.
        ascii_ratio = sum(1 for ch in quote if ord(ch) < 128) / max(len(quote), 1)
        return ascii_ratio >= 0.9

    try:
        return detect(quote) == "en"
    except Exception:
        return False


def _review_text(row: pd.Series) -> str:
    for col in ("verbatim_quote", "unmet_need", "pain_category"):
        val = row.get(col)
        if val is not None and str(val).strip().lower() not in {"", "none", "nan"}:
            return str(val).strip()
    return ""


def _has_min_words(text: str, min_words: int = 5) -> bool:
    """Keep reviews with more than 4 words (i.e. at least 5)."""
    return len(text.split()) >= min_words


def build_insights() -> Path:
    src = ROOT / "data" / "processed" / "insights.csv"
    if not src.exists():
        raise FileNotFoundError(f"Missing {src} — run Phase 2 first.")

    df = pd.read_csv(src)
    df = df.drop_duplicates(subset=["review_id"], keep="first").reset_index(drop=True)

    lang_map = _load_lang_map()
    english_mask = df.apply(
        lambda row: _is_english(str(row["review_id"]), row.get("verbatim_quote"), lang_map),
        axis=1,
    )
    before = len(df)
    df = df[english_mask].reset_index(drop=True)
    print(f"English-only filter: kept {len(df)} / {before} reviews")

    before_words = len(df)
    word_mask = df.apply(lambda row: _has_min_words(_review_text(row)), axis=1)
    df = df[word_mask].reset_index(drop=True)
    print(f"Min words filter (>4 words): kept {len(df)} / {before_words} reviews")

    def _sentiment_intensity(s) -> int:
        return SENTIMENT_SCORE.get(str(s).strip().lower(), 3)

    def _is_rep(row) -> bool:
        text = f"{row.get('unmet_need', '')} {row.get('verbatim_quote', '')}".lower()
        cat = str(row.get("pain_category", "")).lower()
        return cat in {"recommendation_quality", "listening_behavior"} or "repeat" in text or "shuffle" in text

    out = pd.DataFrame({
        "review_id": df["review_id"],
        "source": df["source"],
        "sentiment": df["sentiment"].astype(str).str.lower(),
        "country": None,
        "rating": None,
        "pain_category": df["pain_category"],
        "specific_pain": df["unmet_need"].where(
            df["unmet_need"].astype(str).str.lower().ne("none"), df["pain_category"]
        ),
        "verbatim_quote": df["verbatim_quote"],
        "sentiment_intensity": df["sentiment"].map(_sentiment_intensity),
        "geography": None,
        "language_preference": "en",
        "listening_style": df["segment"],
        "unmet_need": df["unmet_need"],
        "user_suggested_fix": df["unmet_need"],
        "url": None,
        "is_discovery_related": df["discovery_related"].astype(bool),
        "is_repetition_related": df.apply(_is_rep, axis=1),
    })

    dest = OUT / f"insights_{STAMP}.csv"
    out.to_csv(dest, index=False)
    print(f"Wrote {len(out)} insights -> {dest}")
    return dest


def build_themes() -> Path:
    topics_path = ROOT / "data" / "processed" / "topics.csv"
    synthesis_path = ROOT / "data" / "synthesis" / "synthesis_report.json"

    themes: list[dict] = []
    segment_breakdown: dict = {}

    if topics_path.exists():
        tdf = pd.read_csv(topics_path)
        tdf = tdf[tdf["topic_id"] >= 0].sort_values("size", ascending=False)
        for _, row in tdf.iterrows():
            quotes = _split_list(row.get("representative_quotes"))
            keywords = _split_list(row.get("keywords"))
            top_needs = ", ".join(keywords[:5]) if keywords else "See representative quotes"
            themes.append({
                "theme_id": f"T{int(row['topic_id'])}",
                "theme_name": str(row["label"]),
                "one_line_summary": str(row["label"]),
                "estimated_frequency_pct": round(float(row["share_pct"]), 1),
                "dominant_segment": str(row.get("top_segment") or "unknown"),
                "severity": SEVERITY_FROM_SENTIMENT.get(str(row.get("top_sentiment", "neutral")).lower(), 3),
                "representative_quotes": quotes[:5],
                "root_cause_hypothesis": (
                    f"Cluster driven by: {', '.join(keywords[:8])}" if keywords else "See pain category distribution."
                ),
                "what_users_want_instead": top_needs,
            })
        segment_breakdown = {
            str(row["top_segment"]): int(row["size"])
            for _, row in tdf.groupby("top_segment", as_index=False)["size"].sum().iterrows()
        }
    elif synthesis_path.exists():
        data = json.loads(synthesis_path.read_text(encoding="utf-8"))
        for i, pt in enumerate(data.get("pain_themes", [])[:15], start=1):
            themes.append({
                "theme_id": f"T{i}",
                "theme_name": str(pt["pain_category"]).replace("_", " ").title(),
                "one_line_summary": f"{pt['review_count']} reviews · {pt['discovery_overlap_pct']}% discovery overlap",
                "estimated_frequency_pct": round(100 * pt["review_count"] / max(1, data["summary"]["total_reviews_analyzed"]), 1),
                "dominant_segment": max(pt.get("segments_affected", {}), key=pt.get("segments_affected", {}).get, default="unknown"),
                "severity": min(5, max(1, int(pt.get("negative_ratio", 0.5) * 5))),
                "representative_quotes": pt.get("evidence_quotes", [])[:5],
                "root_cause_hypothesis": f"Primary pain category: {pt['pain_category']}",
                "what_users_want_instead": ", ".join(list(pt.get("top_unmet_needs", {}).keys())[:3]),
            })
        segment_breakdown = data.get("summary", {}).get("segment_distribution", {})

    payload = {"themes": {"themes": themes}, "segment_breakdown": segment_breakdown}
    dest = OUT / f"themes_{STAMP}.json"
    dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(themes)} themes -> {dest}")
    return dest


def build_report() -> Path:
    candidates = [
        ROOT / "data" / "synthesis" / "synthesis_report.md",
        ROOT / "docs" / "problemstatement.md",
    ]
    for src in candidates:
        if src.exists():
            dest = OUT / f"discovery_insights_report_{STAMP}.md"
            shutil.copy2(src, dest)
            print(f"Wrote report -> {dest}")
            return dest
    dest = OUT / f"discovery_insights_report_{STAMP}.md"
    dest.write_text("# Spotify Discovery Insights\n\nReport not yet generated.\n", encoding="utf-8")
    return dest


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    build_insights()
    build_themes()
    build_report()
    print("Backend data ready.")


if __name__ == "__main__":
    main()
