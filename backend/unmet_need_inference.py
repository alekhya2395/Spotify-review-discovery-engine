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


# ---------------------------------------------------------------------------
# Strategic rewrite — convert feature-oriented phrases to user motivations.
# Runs AFTER initial extraction so both Phase-2 LLM outputs and inferred
# phrases get reframed (e.g., "Need offline mode" -> "Need uninterrupted
# listening when offline"). First match wins.
# ---------------------------------------------------------------------------

_STRATEGIC_REWRITE_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    # ----- Discovery & exploration -----
    (re.compile(r"\baccess\s*(?:to\s+)?'?what.?s\s+new'?\s*feature\b", re.I),
     "Need easier visibility into new releases"),
    (re.compile(r"\brestore\s*'?(?:new\s+)?releases'?\s+feature\b", re.I),
     "Need easier visibility into new releases"),
    (re.compile(r"\bnew\s+album\s+releases?\b", re.I),
     "Need easier visibility into new releases"),
    (re.compile(r"\bdiscover\s+music\s+from\s+\w+(?:\s+and\s+\w+)*", re.I),
     "Need exposure to music beyond the default catalog"),
    (re.compile(r"\bmore\s+songs\s+like\b", re.I),
     "Need exposure to similar but unfamiliar music"),
    (re.compile(r"\b(?:method|way)\s+(?:for|to)\s+find(?:ing)?\s+new\s+music\b", re.I),
     "Need guided discovery beyond existing listening habits"),
    (re.compile(r"^need\s+(?:music\s+)?discovery\.?$", re.I),
     "Need easier music discovery"),
    (re.compile(r"\bartist\s+discovery\b", re.I),
     "Need easier artist discovery"),
    (re.compile(r"\bdiscover(?:y)?\s+of\s+new\s+music\b", re.I),
     "Need guided discovery beyond existing listening habits"),
    (re.compile(r"\balgorithm[-\s]*free\s+music\s+discovery\b", re.I),
     "Need confidence when exploring new music"),
    (re.compile(r"\bsimilar\s+music\s+recommend", re.I),
     "Need recommendations balancing familiarity and novelty"),
    (re.compile(r"\bimprove(?:d)?\s+music\s+discovery\b", re.I),
     "Need easier music discovery"),
    (re.compile(r"\bimproved\s+discover\s*weekly\b", re.I),
     "Need fresher and more accurate Discover Weekly"),
    (re.compile(r"\bautomagic\s+playlist\b", re.I),
     "Need personalized playlists that surface fresh music"),
    (re.compile(r"\bimproved\s+playlist\s+curation\b", re.I),
     "Need stronger curated discovery playlists"),
    (re.compile(r"^need\s+curated\s+playlists?\.?$", re.I),
     "Need stronger curated discovery playlists"),
    (re.compile(r"^need\s+more\s+(?:song|music)\s+recommendations?\.?$", re.I),
     "Need exposure to more relevant music"),
    (re.compile(r"\bmore\s+personalized\s+recommendations?\b", re.I),
     "Need better personalization"),
    (re.compile(r"\bmore\s+accurate\s+recommendations?\b", re.I),
     "Need fresher and more accurate recommendations"),
    (re.compile(r"\b(?:cantonese|spanish|french|german|hindi|tamil|telugu|korean|japanese|portuguese|mandarin|chinese|arabic|punjabi|bengali|urdu|swahili|afrikaans|regional|local|country|language)\b.*\b(?:music|discover|recommend|playlist|songs?)\b", re.I),
     "Need regional and language-specific discovery"),
    (re.compile(r"\b(?:underground|emerging|niche|unfamiliar|indie)\b.*\b(?:music|artist|song|genre)\b", re.I),
     "Need exposure to unfamiliar genres"),
    (re.compile(r"\bmore\s+diverse\s+recommendations?\b", re.I),
     "Need more diverse recommendations"),
    (re.compile(r"\bavoid\s+repetitive\s+songs?\b", re.I),
     "Need more diverse recommendations"),
    (re.compile(r"\bkid[-\s]?friendly\b", re.I),
     "Need safer family-oriented listening experiences"),

    # ----- Ads -----
    (re.compile(
        r"\b(?:remove\s+ads(?:\s+for\s+free\s+users)?|reduce\s+ads|reduced\s+ads|"
        r"fewer\s+ads|less\s+ads|less\s+frequent\s+ads|no\s+ads|"
        r"ad[-\s]?free(?:\s+experience|\s+listening)?)\b",
        re.I,
    ), "Need a less interruptive free-tier experience"),
    (re.compile(r"\b(?:choose|select|pick)\s+songs?\s+without\s+ads\b", re.I),
     "Need a less interruptive free-tier experience"),

    # ----- Pricing -----
    (re.compile(r"\baccess\s+to\s+premium\s+features?\s+without\s+paying\b", re.I),
     "Need an affordable path to premium-only features"),
    (re.compile(r"\baffordable\s+pricing\b", re.I),
     "Need a more affordable plan that matches value"),
    (re.compile(r"\bfree\s+version\b", re.I),
     "Need a usable free experience without aggressive upsell"),
    (re.compile(r"\bmore\s+skips\b", re.I),
     "Need a less restrictive free-tier playback experience"),

    # ----- Performance / stability -----
    (re.compile(
        r"\b(?:stable\s+app|more\s+stable\s+app|app\s+to\s+not\s+crash|"
        r"fix\s+app\s+crashes?|improve\s+app\s+performance|fix\s+bugs?|"
        r"fix\s+freezing|fix\s+lag)\b",
        re.I,
    ), "Need a crash-free app experience"),

    # ----- Cross-device / Connect / Cast -----
    (re.compile(r"\b(?:google\s*cast|spotify\s*connect|chromecast|airplay)\b", re.I),
     "Need reliable cross-device playback control"),

    # ----- Offline -----
    (re.compile(r"\boffline\s+(?:mode|listening|download|support|playback)?\b", re.I),
     "Need uninterrupted listening when offline"),

    # ----- Late-pass cleanups for feature-specific phrasing -----
    (re.compile(r"\b(?:premium\s+should\s+be\s+free|free\s+premium|premium\s+free)\b", re.I),
     "Need an affordable path to premium-only features"),
    (re.compile(r"\b(?:skip\s+ads|more\s+skip)\b", re.I),
     "Need a less restrictive free-tier playback experience"),
    (re.compile(r"\bno\s+price\s+increase", re.I),
     "Need a more affordable plan that matches value"),
    (re.compile(r"\baffordable\s+premium\s+option\b", re.I),
     "Need a more affordable plan that matches value"),
    (re.compile(r"\brestore\s*'?[\w\s]+'?\s*(?:category|feature|section|tab)\b", re.I),
     "Need stable, predictable UI changes"),
    (re.compile(r"^need\s+(?:more\s+)?music\s+recommendations?\.?$", re.I),
     "Need exposure to more relevant music"),
    (re.compile(
        r"\bmore\s+(?:[a-z]+(?:[-/][a-z]+)?\s+)?(?:music|songs?|artists?)\s+"
        r"(?:in|on)\s+discover\s*weekly\b",
        re.I,
    ), "Need broader genre coverage in personalized playlists"),
    (re.compile(r"\bability\s+to\s+personalize\s+home\s+screen\b", re.I),
     "Need a more personalized home experience"),
    (re.compile(r"\bability\s+to\s+(?:add|remove)\s+(?:missing\s+)?songs?\s+to\s+playlists?\b", re.I),
     "Need control over what's surfaced in personalized playlists"),
)

# Canonical-form mapping for hard dedup. After strategic_rewrite the phrase is
# usually one of these strategic forms; near-duplicates collapse to the same
# bucket so downstream counting and ranking treat them as one.
_CANONICAL_NEEDS: dict[str, str] = {
    # Discovery
    "need easier music discovery": "Need easier music discovery",
    "need easier discovery": "Need easier music discovery",
    "need simpler discovery": "Need easier music discovery",
    "need better discovery": "Need easier music discovery",
    "need guided music discovery": "Need guided discovery beyond existing listening habits",
    "need guided discovery beyond existing listening habits": "Need guided discovery beyond existing listening habits",
    "need easier artist discovery": "Need easier artist discovery",
    "need artist discovery": "Need easier artist discovery",
    "need easier visibility into new releases": "Need easier visibility into new releases",
    "need exposure to unfamiliar genres": "Need exposure to unfamiliar genres",
    "need exposure to similar but unfamiliar music": "Need exposure to similar but unfamiliar music",
    "need exposure to more relevant music": "Need exposure to more relevant music",
    "need exposure to music beyond the default catalog": "Need exposure to music beyond the default catalog",
    "need confidence when exploring new music": "Need confidence when exploring new music",
    "need recommendations balancing familiarity and novelty": "Need recommendations balancing familiarity and novelty",
    "need more diverse recommendations": "Need more diverse recommendations",
    "need stronger curated discovery playlists": "Need stronger curated discovery playlists",
    "need fresher and more accurate recommendations": "Need fresher and more accurate recommendations",
    "need fresher and more accurate discover weekly": "Need fresher and more accurate Discover Weekly",
    "need better personalization": "Need better personalization",
    "need more personalized recommendations": "Need better personalization",
    "need personalized playlists that surface fresh music": "Need personalized playlists that surface fresh music",
    "need regional and language-specific discovery": "Need regional and language-specific discovery",
    "need broader genre coverage in personalized playlists": "Need broader genre coverage in personalized playlists",
    "need control over what's surfaced in personalized playlists": "Need control over what's surfaced in personalized playlists",
    "need a more personalized home experience": "Need a more personalized home experience",
    "need dedicated discovery surfaces": "Need a dedicated discovery surface beyond Discover Weekly",
    "need a dedicated discovery surface beyond discover weekly": "Need a dedicated discovery surface beyond Discover Weekly",
    "need mood-aware listening sessions": "Need mood and context-aware recommendations",
    "need mood- and activity-based listening modes": "Need mood and context-aware recommendations",
    "need mood and context-aware recommendations": "Need mood and context-aware recommendations",

    # Ads / pricing
    "need a less interruptive free-tier experience": "Need a less interruptive free-tier experience",
    "need an ad-free listening option without paying full price": "Need a less interruptive free-tier experience",
    "need fewer ads": "Need a less interruptive free-tier experience",
    "need no ads": "Need a less interruptive free-tier experience",
    "need a more affordable plan that matches value": "Need a more affordable plan that matches value",
    "need clearer value from premium": "Need clearer value from Premium",
    "need an affordable path to premium-only features": "Need an affordable path to premium-only features",
    "need a usable free experience without aggressive upsell": "Need a usable free experience without aggressive upsell",
    "need a less restrictive free-tier playback experience": "Need a less restrictive free-tier playback experience",
    "need simpler family and student plan policies": "Need simpler family and student plan policies",

    # Performance / reliability
    "need a crash-free app experience": "Need a crash-free app experience",
    "need a stable, fast app experience": "Need a crash-free app experience",
    "need a faster, responsive app": "Need a faster, responsive app",
    "need reliable wireless audio playback": "Need reliable wireless audio playback",
    "need reliable cross-device playback control": "Need reliable cross-device playback control",
    "need uninterrupted listening when offline": "Need uninterrupted listening when offline",
    "need better offline listening support": "Need uninterrupted listening when offline",
    "need reliable offline downloads": "Need uninterrupted listening when offline",
    "need better battery efficiency": "Need better battery efficiency",

    # UI / search / library / catalog
    "need a simpler, more intuitive interface": "Need a simpler, more intuitive interface",
    "need simpler navigation": "Need a simpler, more intuitive interface",
    "need stable, predictable ui changes": "Need stable, predictable UI changes",
    "need stronger library management": "Need stronger library management",
    "need a more accurate and powerful search": "Need a more accurate and powerful search",
    "need broader catalog availability": "Need broader catalog availability",
    "need full catalog availability in my region": "Need broader catalog availability",
    "need a richer spoken-word catalog and experience": "Need a richer spoken-word catalog and experience",
    "need better audio quality controls": "Need better audio quality controls",

    # Behavior / modes
    "need better shuffle controls": "Need smarter shuffle and autoplay",
    "need a smarter, truly random shuffle": "Need smarter shuffle and autoplay",
    "need better queue and playback control": "Need better queue and playback control",
    "need easier playlist management": "Need easier playlist management",
    "need workout-friendly listening modes": "Need mood and context-aware recommendations",
    "need safer family-oriented listening experiences": "Need safer family-oriented listening experiences",
    "need better listening modes and session control": "Need better listening modes and session control",
    "need richer social listening and sharing features": "Need richer social listening and sharing features",

    # Generic / preserve-the-good
    "need to preserve current recommendation quality": "Need to preserve the positives users already value",
    "need to preserve the positives users already value": "Need to preserve the positives users already value",
    "need a more reliable music experience": "Need a more reliable music experience",
}

# Discovery-focused unmet needs (used for prioritization in answers).
DISCOVERY_FOCUSED_NEEDS: frozenset[str] = frozenset({
    "Need easier music discovery",
    "Need easier artist discovery",
    "Need easier visibility into new releases",
    "Need guided discovery beyond existing listening habits",
    "Need exposure to unfamiliar genres",
    "Need exposure to similar but unfamiliar music",
    "Need exposure to more relevant music",
    "Need exposure to music beyond the default catalog",
    "Need confidence when exploring new music",
    "Need recommendations balancing familiarity and novelty",
    "Need more diverse recommendations",
    "Need stronger curated discovery playlists",
    "Need fresher and more accurate recommendations",
    "Need fresher and more accurate Discover Weekly",
    "Need better personalization",
    "Need personalized playlists that surface fresh music",
    "Need a dedicated discovery surface beyond Discover Weekly",
    "Need regional and language-specific discovery",
    "Need broader genre coverage in personalized playlists",
    "Need control over what's surfaced in personalized playlists",
    "Need mood and context-aware recommendations",
})


_TRAILING_TAG_RE = re.compile(r"\s*\((?:general|broad|other|catch[-\s]?all|misc)\)\s*$", re.I)


def strategic_rewrite(text: str) -> str:
    """Map feature-oriented phrasing to motivation-driven phrasing.

    Returns the canonical strategic phrase when one is known; otherwise
    returns the input normalized via ``_normalize_phrase``.
    """
    cleaned = _normalize_phrase(text)
    cleaned = _TRAILING_TAG_RE.sub("", cleaned).strip()
    for pattern, target in _STRATEGIC_REWRITE_RULES:
        if pattern.search(cleaned):
            cleaned = target
            break
    return _CANONICAL_NEEDS.get(cleaned.lower(), cleaned)


# Phrases that look like "Need …" but actually praise the product. These are
# strengths, not unmet needs — chat answers should never surface them in the
# Unmet Needs section.
NON_UNMET_NEED_LABELS: frozenset[str] = frozenset({
    "Need to preserve the positives users already value",
    "Need to preserve current recommendation quality",
})


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
    """Return a non-empty, motivation-driven unmet-need phrase for a review."""
    if not _is_empty(existing):
        return strategic_rewrite(str(existing))

    blob = " ".join(
        str(v) for v in (verbatim_quote, specific_pain, listening_style)
        if not _is_empty(v)
    ).strip()

    if blob:
        for pattern, phrase in _KEYWORD_PATTERNS:
            if pattern.search(blob):
                return strategic_rewrite(phrase)

    key = str(pain_category or "").strip().lower()
    if key in _PAIN_CATEGORY_DEFAULTS:
        return strategic_rewrite(_PAIN_CATEGORY_DEFAULTS[key])

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
