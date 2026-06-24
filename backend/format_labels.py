"""Professional label formatting & curation helpers for chat answers."""

from __future__ import annotations

import re
from typing import Iterable

PAIN_LABELS: dict[str, str] = {
    "recommendation_quality": "Algorithm & Recommendations",
    "algorithm_repetition": "Algorithm & Recommendations",
    "ui_ux": "UI/UX Issues",
    "ui_ux_issues": "UI/UX Issues",
    "pricing": "Pricing & Value",
    "pricing_complaints": "Pricing & Value",
    "content_availability": "Catalog & Availability",
    "catalog_gaps": "Catalog & Availability",
    "listening_behavior": "Listening Behavior",
    "social_features": "Social Features",
    "discovery": "Music Discovery",
    "performance": "Performance & Stability",
    "ads": "Ads & Free Tier",
    "audio_quality": "Audio Quality",
    "none": "General Feedback",
}

PAIN_INSIGHT: dict[str, str] = {
    "discovery": "Users want fresher, more diverse music surfaces beyond Discover Weekly and repeat-heavy autoplay.",
    "recommendation_quality": "Recommendation feeds feel stale, repetitive, or off-target; users want more relevant, diverse picks.",
    "algorithm_repetition": "The algorithm cycles the same artists; users want broader rotation and better diversity controls.",
    "ui_ux": "Navigation friction around saving, sharing, and exploring related artists slows down discovery.",
    "ui_ux_issues": "Navigation friction around saving, sharing, and exploring related artists slows down discovery.",
    "pricing": "Premium pricing, family plan policies, and student verification are common churn signals.",
    "pricing_complaints": "Premium pricing, family plan policies, and student verification are common churn signals.",
    "listening_behavior": "Users want better support for varied modes — focus, shuffle, autoplay — with smarter session continuity.",
    "social_features": "Sharing, collaborative playlists, and social discovery surfaces feel underdeveloped.",
    "content_availability": "Specific tracks, podcasts, or regional content are reported as missing.",
    "performance": "App crashes, slow loads, and playback hiccups are damaging trust on key flows.",
    "ads": "Ad frequency and length on the free tier is the primary churn complaint from non-payers.",
    "audio_quality": "Audio quality on low-tier plans and Bluetooth handoff is a recurring complaint.",
}

QUESTION_TOPICS: dict[str, tuple[str, ...]] = {
    "discovery": ("discover", "find", "new music", "fresh", "recommend", "explore", "autoplay",
                  "playlist", "discover weekly", "algorithm", "skip", "dismiss", "reject",
                  "suggestion", "radio", "mix", "improve discovery"),
    "pricing": ("price", "pricing", "cost", "premium", "subscription", "expensive", "cheap",
                "family plan", "student", "free", "paywall", "ads", "ad ", "pay", "worth",
                "money", "tier"),
    "ui": ("ui", "ux", "interface", "design", "navigation", "layout", "menu", "button",
           "confusing", "hard to find", "usability", "screen", "update", "redesign"),
    "performance": ("crash", "bug", "slow", "lag", "loading", "freeze", "stutter", "performance",
                    "stability", "glitch", "not working", "freeze", "buffer"),
    "social": ("social", "share", "collaborate", "friend", "group", "playlist sharing",
               "together", "follow", "community"),
    "catalog": ("catalog", "library", "missing", "song not", "track not", "podcast", "audiobook",
                "unavailable", "region"),
    "audio": ("audio", "sound", "quality", "bitrate", "bluetooth", "headphone", "speaker",
              "volume", "lossless"),
    "segment": ("segment", "user type", "persona", "audience", "demographic", "casual",
                "power user", "new user", "free tier user"),
    "repetition": ("repeat", "repetitive", "repeatedly", "same content", "same songs", "same artists",
                   "same music", "same playlist", "over and over", "again and again", "monoton",
                   "listen to the same", "stuck listening", "re-listen"),
}

FOCUS_AREA_BY_TOPIC: dict[str, tuple[str, ...]] = {
    "discovery": (
        "Build exploration surfaces that surface unfamiliar artists outside listening history.",
        "Add user controls for how adventurous algorithmic playlists should be.",
        "Inject intentional novelty into autoplay, radio, and home feeds.",
    ),
    "repetition": (
        "Detect repetitive listening loops and offer timely nudges toward fresh content.",
        "Balance engagement optimization with explicit diversity and novelty goals.",
        "Redesign autoplay to mix familiar comfort tracks with gradual novelty.",
    ),
    "pricing": (
        "Clarify Premium value with benefits users can perceive immediately.",
        "Rebalance free-tier ad load so discovery sessions feel less punitive.",
        "Simplify family and student plan enrollment and verification.",
    ),
    "ui": (
        "Flatten navigation for save, share, queue, and artist exploration flows.",
        "Improve library organization for large collections and playlists.",
        "Roll out major UI changes gradually with clearer migration paths.",
    ),
    "performance": (
        "Treat playback reliability and crash-free sessions as top-line metrics.",
        "Optimize load times on library, search, and playlist screens.",
        "Improve Bluetooth reconnection and wireless playback consistency.",
    ),
    "social": (
        "Expand collaborative playlists and friend-driven discovery surfaces.",
        "Reduce friction for in-app and external music sharing.",
        "Test community spaces around genres, moods, or local scenes.",
    ),
    "catalog": (
        "Surface catalog availability transparently in search and browse.",
        "Close high-friction regional and spoken-word catalog gaps.",
        "Separate music and podcast discovery where users want focus.",
    ),
    "audio": (
        "Make audio quality settings easier to find and understand.",
        "Improve perceived quality on common wireless listening setups.",
        "Evaluate bitrate and codec improvements users notice on Premium.",
    ),
    "segment": (
        "Tailor onboarding and recommendations by listening style and tenure.",
        "Provide deeper discovery tools for power listeners versus casual users.",
        "Reduce free-tier friction in flows that support eventual conversion.",
    ),
    "general": (
        "Prioritize product work that directly addresses the question asked.",
        "Ship visible improvements in discovery control and recommendation freshness.",
        "Track emerging complaint themes over time to catch regressions early.",
    ),
}

OFF_TOPIC_MARKERS = (
    "concert",
    "festival",
    "solstice",
    "#np",
    "nowplaying",
    "youtu.be",
    "mastomusic",
    "crash a blues night",
    "punk anthem",
    "tour date",
    "live show",
    "vinyl",
    "album release party",
)

SPOTIFY_SIGNAL_WORDS = (
    "spotify",
    "playlist",
    "premium",
    "discover weekly",
    "release radar",
    "autoplay",
    "shuffle",
    "podcast",
    "app",
    "algorithm",
    "recommend",
)


def detect_topic(question: str) -> str:
    """Return the dominant pain topic for the question (or 'general')."""
    q = (question or "").lower()
    scored: list[tuple[int, str]] = []
    for topic, terms in QUESTION_TOPICS.items():
        hits = sum(1 for term in terms if term in q)
        if hits:
            scored.append((hits, topic))
    if not scored:
        return "general"
    scored.sort(reverse=True)
    return scored[0][1]


def format_pain(value: str) -> str:
    key = str(value or "").lower().strip()
    if not key or key in {"none", "nan"}:
        return "General Feedback"
    return PAIN_LABELS.get(key, key.replace("_", " ").title())


def format_segment(value: str) -> str:
    if not value or str(value).lower() in {"unknown", "none", "nan"}:
        return "All Users"
    return str(value).replace("_", " ").title()


def is_noisy_theme(name: str) -> bool:
    """Skip raw BERTopic keyword strings unsuitable for user-facing output."""
    text = str(name or "").strip().lower()
    if not text or len(text) < 4:
        return True
    if text.count("/") >= 2:
        return True
    tokens = re.split(r"[\s/]+", text)
    if len(tokens) >= 3 and len(set(tokens)) <= max(2, len(tokens) // 2):
        return True
    return bool(re.search(r"\b(\w+)\s+\1\b", text))


def quote_relevance(quote: str, topic: str) -> int:
    """Score a quote for relevance to the topic; reject off-topic noise."""
    text = (quote or "").strip().lower()
    words = text.split()
    if len(words) < 6 or len(words) > 80:
        return -5

    for marker in OFF_TOPIC_MARKERS:
        if marker in text:
            return -10

    score = 0
    topic_terms = QUESTION_TOPICS.get(topic, ())
    for term in topic_terms:
        if term in text:
            score += 3

    for word in SPOTIFY_SIGNAL_WORDS:
        if word in text:
            score += 1

    if "spotify" in text:
        score += 2

    return score


def curated_quotes(
    reviews: list[dict],
    question: str,
    limit: int = 4,
    min_score: int = 1,
) -> list[str]:
    """Return formatted, topic-relevant verbatim quotes with source labels."""
    topic = detect_topic(question)
    scored: list[tuple[int, dict]] = []
    seen_quotes: set[str] = set()

    for row in reviews:
        quote = (row.get("quote") or "").strip()
        if not quote:
            continue
        norm = quote.lower()[:120]
        if norm in seen_quotes:
            continue
        seen_quotes.add(norm)
        score = quote_relevance(quote, topic)
        if score < min_score:
            continue
        scored.append((score, row))

    scored.sort(key=lambda x: x[0], reverse=True)

    lines: list[str] = []
    for _, row in scored[:limit]:
        quote = (row.get("quote") or "").strip()
        if len(quote) > 240:
            quote = quote[:237].rsplit(" ", 1)[0] + "..."
        src = row.get("source") or "User review"
        seg = format_segment(row.get("segment") or "")
        label = src if seg == "All Users" else f"{src} | {seg}"
        lines.append(f'> "{quote}"\n> — {label}')
    return lines


def pain_lines(
    stats: dict,
    question: str,
    limit: int = 5,
    require_relevant: bool = True,
) -> list[tuple[str, str, int]]:
    """Return (key, label, count) tuples ranked by relevance to the question."""
    raw = stats.get("top_pain_categories") or {}
    items = [(k, int(v)) for k, v in raw.items() if str(k).lower() not in {"none", "nan", ""}]
    if not items:
        return []

    topic = detect_topic(question)
    topic_priority: dict[str, list[str]] = {
        "discovery": ["discovery", "recommendation_quality", "algorithm_repetition", "listening_behavior"],
        "repetition": ["algorithm_repetition", "recommendation_quality", "listening_behavior", "discovery"],
        "pricing": ["pricing", "pricing_complaints", "ads"],
        "ui": ["ui_ux", "ui_ux_issues"],
        "performance": ["performance"],
        "social": ["social_features"],
        "catalog": ["content_availability", "catalog_gaps"],
        "audio": ["audio_quality"],
        "segment": ["listening_behavior", "discovery", "ads", "pricing"],
        "general": [],
    }
    priority = topic_priority.get(topic, [])

    def rank_key(kv: tuple[str, int]) -> tuple[int, int]:
        key, count = kv
        try:
            pos = priority.index(key)
        except ValueError:
            pos = 99
        return (pos, -count)

    ranked = sorted(items, key=rank_key)

    if require_relevant and priority:
        relevant = [kv for kv in ranked if kv[0] in priority]
        rest = [kv for kv in ranked if kv[0] not in priority]
        ranked = relevant + rest

    return [(k, format_pain(k), n) for k, n in ranked[:limit]]


def pain_insights(pain_keys: Iterable[str]) -> list[str]:
    """Return product-focus bullets for a list of pain keys."""
    out: list[str] = []
    seen: set[str] = set()
    for key in pain_keys:
        insight = PAIN_INSIGHT.get(str(key).lower())
        if insight and insight not in seen:
            seen.add(insight)
            out.append(insight)
    return out
