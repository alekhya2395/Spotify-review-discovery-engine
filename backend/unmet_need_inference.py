"""Infer a concrete unmet need for every review.

Never returns "none". When the Phase-2 LLM extracted "none" (or empty), this
module derives a canonical user goal from the review text and pain category.

Order of precedence:
1. Keyword/phrase pattern matches against `verbatim_quote` + `specific_pain`
   (most specific signal wins).
2. Pain-category default — broad goal aligned with that category.
3. Hard fallback — generic but still actionable ("Need a more reliable music
   experience").

The output is a short, third-person goal in the form `Need <something>` so it
reads cleanly anywhere the engine surfaces unmet needs.
"""

from __future__ import annotations

import re
from typing import Iterable

import pandas as pd

# Strings we treat as "missing" — these get re-inferred.
_EMPTY_TOKENS = frozenset({"", "none", "nan", "n/a", "na", "null", "unknown", "not specified"})

# Keyword/pattern matches: each pattern -> canonical Need phrase.
# Ordered most-specific to most-generic; the first match wins.
_KEYWORD_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # ---- Recommendation / personalization ----
    (re.compile(r"\b(?:same|repeat|repetitive|over and over|monoton|loop|stuck)\b.*\b(?:song|track|artist|music|playlist)\b", re.I),
     "Need more diverse recommendations"),
    (re.compile(r"\b(?:same|repeat|repetitive|over and over|monoton|loop|stuck)\b", re.I),
     "Need more diverse recommendations"),
    (re.compile(r"\birrelevant|wrong\s+(?:song|artist|recommendation|suggestion)\b", re.I),
     "Need better personalization"),
    (re.compile(r"\b(?:bad|poor|terrible|awful)\s+(?:recommend|suggestion|algorithm|mix)", re.I),
     "Need better personalization"),
    (re.compile(r"\b(?:hate|don.?t like|dislike)\b.*\b(?:recommend|playlist|mix|radio)\b", re.I),
     "Need better personalization"),
    (re.compile(r"\b(?:recommend\w*|suggest\w*|algorithm)\b.*\b(?:stale|same|repetitive|boring|miss|off|poor|bad)\b", re.I),
     "Need fresher and more accurate recommendations"),

    # ---- Discovery ----
    (re.compile(r"\b(?:hard|difficult|can.?t|cannot|unable)\b.*\b(?:find|discover|explore)\b.*\b(?:new|fresh|different|unfamiliar|artist|song|music)\b", re.I),
     "Need guided music discovery"),
    (re.compile(r"\b(?:no way|nowhere)\b.*\b(?:explore|discover)\b", re.I),
     "Need dedicated discovery surfaces"),
    (re.compile(r"\b(?:want|wish|need|hope)\b.*\b(?:new|fresh|different|underground|emerging|niche)\b.*\b(?:music|artist|song|track|genre)\b", re.I),
     "Need easier access to fresh and diverse music"),
    (re.compile(r"\b(?:discover\s*weekly|release\s*radar|daily\s*mix|made\s*for\s*you)\b", re.I),
     "Need stronger curated discovery playlists"),
    (re.compile(r"\b(?:discover|exploration|exploring)\b", re.I),
     "Need easier music discovery"),

    # ---- Shuffle / playlist control ----
    (re.compile(r"\bshuffle\b.*\b(?:broken|bad|same|repeat|not\s*random|biased)\b", re.I),
     "Need a smarter, truly random shuffle"),
    (re.compile(r"\bshuffle\b", re.I),
     "Need better shuffle controls"),
    (re.compile(r"\b(?:queue|play\s*next|play\s*after|reorder)\b", re.I),
     "Need better queue and playback control"),
    (re.compile(r"\b(?:playlist)\b.*\b(?:manage|organi[sz]e|edit|sort|delete|create|share)\b", re.I),
     "Need easier playlist management"),

    # ---- Ads / pricing ----
    (re.compile(r"\b(?:too many|so many|constant|endless|loud)\s+ads?\b", re.I),
     "Need a less interruptive free-tier experience"),
    (re.compile(r"\bads?\b.*\b(?:interrupt|disrupt|annoy|loud|long|frequent|skip)\b", re.I),
     "Need a less interruptive free-tier experience"),
    (re.compile(r"\bad\s*free\b|\bremove\s+ads?\b|\bno\s+ads?\b", re.I),
     "Need an ad-free listening option without paying full price"),
    (re.compile(r"\b(?:premium|subscription)\b.*\b(?:expensive|costly|price|worth|value|overpriced)\b", re.I),
     "Need clearer value from Premium"),
    (re.compile(r"\b(?:family|student)\s*plan\b", re.I),
     "Need simpler family and student plan policies"),
    (re.compile(r"\b(?:price|pricing|cost|expensive|cheap|cheaper|free)\b", re.I),
     "Need a more affordable plan that matches value"),

    # ---- Performance / reliability ----
    (re.compile(r"\b(?:crash|crashes|crashed|crashing)\b", re.I),
     "Need a crash-free app experience"),
    (re.compile(r"\b(?:slow|laggy|lag|freeze|frozen|hang|loading|buffer)\b", re.I),
     "Need a faster, responsive app"),
    (re.compile(r"\b(?:bluetooth|airpods|headphone|speaker|disconnect|reconnect)\b", re.I),
     "Need reliable wireless audio playback"),
    (re.compile(r"\b(?:offline|download|cache)\b.*\b(?:fail|broken|disappear|gone|lost|miss)\b", re.I),
     "Need reliable offline downloads"),
    (re.compile(r"\b(?:offline|download)\b", re.I),
     "Need better offline listening support"),
    (re.compile(r"\b(?:battery|drain)\b", re.I),
     "Need better battery efficiency"),

    # ---- Audio quality ----
    (re.compile(r"\b(?:bitrate|lossless|hi\s*-?\s*fi|hi\s*res|audio\s*quality|sound\s*quality)\b", re.I),
     "Need better audio quality controls"),

    # ---- UI / UX ----
    (re.compile(r"\b(?:hard\s+to\s+navigate|confusing|unintuitive|buried|hidden)\b", re.I),
     "Need simpler navigation"),
    (re.compile(r"\b(?:redesign|new\s+design|new\s+update|update\s+ruined|update\s+broke)\b", re.I),
     "Need stable, predictable UI changes"),
    (re.compile(r"\b(?:library|saved\s*music|saved\s*songs|saved\s*albums)\b", re.I),
     "Need stronger library management"),
    (re.compile(r"\b(?:search)\b", re.I),
     "Need a more accurate and powerful search"),

    # ---- Catalog / content ----
    (re.compile(r"\b(?:missing|unavailable|not\s+available|can.?t\s+find)\b.*\b(?:song|album|artist|track|podcast|audiobook)\b", re.I),
     "Need broader catalog availability"),
    (re.compile(r"\b(?:region|country|geo|locale)\b.*\b(?:block|restrict|unavailable|missing)\b", re.I),
     "Need full catalog availability in my region"),
    (re.compile(r"\b(?:podcast|audiobook|spoken)\b", re.I),
     "Need a richer spoken-word catalog and experience"),

    # ---- Social ----
    (re.compile(r"\b(?:friend|social|share|collaborate|together|group)\b", re.I),
     "Need richer social listening and sharing features"),

    # ---- Listening behavior / modes ----
    (re.compile(r"\b(?:workout|gym|run|running|exercise)\b", re.I),
     "Need workout-friendly listening modes"),
    (re.compile(r"\b(?:sleep|relax|focus|study|study\s*session)\b", re.I),
     "Need mood- and activity-based listening modes"),
    (re.compile(r"\b(?:mood|vibe|context|activity)\b", re.I),
     "Need mood-aware listening sessions"),

    # ---- Generic positive / love / works fine ----
    (re.compile(r"\b(?:recommend\w*|playlist|discover\s*weekly)\b.*\b(?:spot[\s-]?on|great|perfect|love|amazing)\b", re.I),
     "Need to preserve current recommendation quality"),
    (re.compile(r"\b(?:i\s+)?(?:love|loved|loving)\b.*\bspotify\b", re.I),
     "Need to preserve the positives users already value"),
    (re.compile(r"\b(?:best|great|awesome|amazing|perfect|fantastic|excellent|wonderful|love it)\b", re.I),
     "Need to preserve the positives users already value"),
    (re.compile(r"\b(?:helpful|useful|works\s+well|works\s+fine|good\s+app)\b", re.I),
     "Need to preserve the positives users already value"),
)

# Pain-category → default user goal when no keyword pattern matches.
_PAIN_CATEGORY_DEFAULTS: dict[str, str] = {
    "recommendation_quality": "Need better personalization",
    "algorithm_repetition": "Need more diverse recommendations",
    "discovery": "Need easier music discovery",
    "listening_behavior": "Need better listening modes and session control",
    "ui_ux": "Need a simpler, more intuitive interface",
    "ui_ux_issues": "Need a simpler, more intuitive interface",
    "pricing": "Need a more affordable plan that matches value",
    "pricing_complaints": "Need a more affordable plan that matches value",
    "ads": "Need a less interruptive free-tier experience",
    "performance": "Need a stable, fast app experience",
    "audio_quality": "Need better audio quality controls",
    "content_availability": "Need broader catalog availability",
    "catalog_gaps": "Need broader catalog availability",
    "social_features": "Need richer social listening and sharing features",
    "none": "Need a more reliable music experience",
}

_DEFAULT_NEED = "Need a more reliable music experience"


def _is_empty(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and pd.isna(value):
        return True
    text = str(value).strip().lower()
    return text in _EMPTY_TOKENS


def _normalize_phrase(text: str) -> str:
    """Make sure the output reads as `Need …` and is single-line."""
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip().rstrip(".")
    if not cleaned:
        return _DEFAULT_NEED
    lower = cleaned.lower()
    if lower in _EMPTY_TOKENS:
        return _DEFAULT_NEED
    if not re.match(r"(?i)^need(?:s|ed)?\b", cleaned):
        cleaned = f"Need {cleaned[0].lower()}{cleaned[1:]}" if cleaned else _DEFAULT_NEED
    return cleaned


def infer_unmet_need(
    *,
    existing: object = None,
    pain_category: object = None,
    verbatim_quote: object = None,
    specific_pain: object = None,
    listening_style: object = None,
) -> str:
    """Return a non-empty unmet-need phrase for a single review."""
    if not _is_empty(existing):
        return _normalize_phrase(str(existing))

    blob = " ".join(
        str(v) for v in (verbatim_quote, specific_pain, listening_style)
        if not _is_empty(v)
    ).strip()

    if blob:
        for pattern, phrase in _KEYWORD_PATTERNS:
            if pattern.search(blob):
                return phrase

    key = str(pain_category or "").strip().lower()
    if key in _PAIN_CATEGORY_DEFAULTS:
        return _PAIN_CATEGORY_DEFAULTS[key]

    return _DEFAULT_NEED


def fill_unmet_needs(df: pd.DataFrame) -> pd.DataFrame:
    """Vectorized application of `infer_unmet_need` over a reviews DataFrame.

    Adds (or rewrites) `unmet_need` so it never contains "none"/NaN.
    """
    if df.empty:
        return df

    out = df.copy()

    if "unmet_need" not in out.columns:
        out["unmet_need"] = ""

    needed_cols: Iterable[str] = ("pain_category", "verbatim_quote", "specific_pain", "listening_style")
    for col in needed_cols:
        if col not in out.columns:
            out[col] = ""

    def _row_need(row: pd.Series) -> str:
        return infer_unmet_need(
            existing=row.get("unmet_need"),
            pain_category=row.get("pain_category"),
            verbatim_quote=row.get("verbatim_quote"),
            specific_pain=row.get("specific_pain"),
            listening_style=row.get("listening_style"),
        )

    out["unmet_need"] = out.apply(_row_need, axis=1)
    return out
