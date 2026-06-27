"""Classify user questions into Spotify music-discovery research categories.

Uses keyword matching, token overlap, and fuzzy phrase matching with a strict
confidence gate. Returns ``None`` when confidence is below ``MIN_CONFIDENCE`` or
the question is out of research scope.
"""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from typing import Any

# ---------------------------------------------------------------------------
# Research categories (evaluation scope)
# ---------------------------------------------------------------------------

MIN_CONFIDENCE = 0.65
MIN_ALIAS_CONFIDENCE = 0.55

CATEGORY_LABELS: dict[str, str] = {
    "music_discovery_challenges": "Music Discovery Challenges",
    "repetitive_listening_behavior": "Repetitive Listening Behavior",
    "playlist_dependency": "Playlist Dependency",
    "recommendation_quality": "Recommendation Quality",
    "user_segments": "User Segments",
    "discovery_frustrations": "Discovery Frustrations",
    "unmet_needs": "Unmet Needs",
    "root_causes": "Root Causes",
    "discovery_journeys": "Discovery Journeys",
    "product_opportunities": "Product Opportunities",
    "ai_assisted_discovery": "AI-Assisted Discovery",
}

# Patterns and canonical example questions per category (longer = higher weight).
_CATEGORY_SIGNALS: dict[str, dict[str, Any]] = {
    "music_discovery_challenges": {
        "patterns": (
            "struggle to discover", "struggle with discovery", "hard to find new",
            "difficult to discover", "discover new music", "find new music",
            "find new artists", "music discovery challenge", "discovery challenge",
            "can't discover", "cannot discover", "explore new music",
            "discovery problem", "discovery barrier", "hard to explore",
        ),
        "examples": (
            "Why do users struggle to discover new music?",
            "What makes music discovery difficult for Spotify users?",
        ),
    },
    "repetitive_listening_behavior": {
        "patterns": (
            "repetitive listening", "repetitive recommendation", "same song",
            "same songs", "same artist", "listen to the same", "over and over",
            "repetition", "repetitive", "repeat", "loop", "monoton",
            "echo chamber", "stuck listening", "hearing the same",
        ),
        "examples": (
            "What causes repetitive listening behavior?",
            "Why are Spotify recommendations repetitive?",
            "Why do users hear the same songs repeatedly?",
        ),
    },
    "playlist_dependency": {
        "patterns": (
            "rely on playlist", "rely heavily on playlist", "heavily on playlist",
            "playlist dependency", "depend on playlist",
            "discover weekly", "release radar", "daily mix", "made for you",
            "curated playlist", "only playlist", "playlist only",
            "heavily on playlists", "playlist-driven",
        ),
        "examples": (
            "Why do users rely heavily on playlists?",
            "How dependent are users on Discover Weekly?",
        ),
    },
    "recommendation_quality": {
        "patterns": (
            "recommendation quality", "recommendation accuracy", "bad recommend",
            "poor recommend", "irrelevant recommend", "wrong recommend",
            "algorithm quality", "personalization quality", "off-target",
            "doesn't understand taste", "recommendation engine",
        ),
        "examples": (
            "Why are recommendations irrelevant?",
            "What drives poor recommendation quality?",
        ),
    },
    "user_segments": {
        "patterns": (
            "user segment", "user segments", "which users", "which user",
            "user type", "user group", "different users", "who experiences",
            "discovery seeker", "playlist user", "heavy listener",
            "casual listener", "premium user", "free user",
            "segment experience", "different discovery challenge",
        ),
        "examples": (
            "Which user segments experience discovery challenges?",
            "Which users experience discovery problems?",
            "Who is most affected by discovery issues?",
        ),
    },
    "discovery_frustrations": {
        "patterns": (
            "discovery frustration", "frustrated with discovery", "frustration",
            "annoyed", "complaint", "complaints", "hate discover",
            "disappoint", "discovery annoy", "negative discovery",
        ),
        "examples": (
            "What discovery frustrations do users report?",
            "What frustrates users about music discovery?",
        ),
    },
    "unmet_needs": {
        "patterns": (
            "unmet need", "unmet needs", "what do users want", "what users need",
            "users ask for", "consistently emerge", "missing feature",
            "wish spotify", "users want", "need emerge",
        ),
        "examples": (
            "What unmet needs emerge consistently across reviews?",
            "What do users need from discovery?",
        ),
    },
    "root_causes": {
        "patterns": (
            "root cause", "root causes", "underlying cause", "why does",
            "what causes", "what cause", "driver", "drivers behind",
            "reason behind", "reasons behind", "cause of discovery problem",
        ),
        "examples": (
            "What are the root causes behind discovery problems?",
            "Why do discovery problems happen?",
        ),
    },
    "discovery_journeys": {
        "patterns": (
            "discovery journey", "discovery path", "discovery flow",
            "how users discover", "discovery process", "exploration journey",
            "discovery experience", "onboarding discovery", "discovery funnel",
        ),
        "examples": (
            "How do users discover new music on Spotify?",
            "What does the discovery journey look like?",
        ),
    },
    "product_opportunities": {
        "patterns": (
            "product opportunity", "product opportunities", "prioritize",
            "product improvement", "product focus", "should spotify",
            "invest in", "roadmap", "what should spotify build",
            "improve spotify", "product bet",
        ),
        "examples": (
            "What product improvements should Spotify prioritize?",
            "What should the product team focus on?",
        ),
    },
    "ai_assisted_discovery": {
        "patterns": (
            "ai-powered discovery", "ai discovery", "ai-assisted",
            "machine learning", "algorithm discovery", "smart discovery",
            "llm discovery", "generative discovery", "ai recommend",
            "artificial intelligence", "ai-powered",
        ),
        "examples": (
            "What opportunities exist for AI-powered discovery?",
            "How could AI improve music discovery?",
        ),
    },
}

# Validated semantic aliases — checked before cluster scoring / out-of-scope rejection.
# Longer phrases are preferred when multiple aliases could match.
_SEMANTIC_ALIASES: dict[str, tuple[str, ...]] = {
    "root_causes": (
        "what are the root causes of discovery problems",
        "what are the root causes behind discovery problems",
        "what are the root causes",
        "what causes discovery problems",
        "why does discovery fail",
    ),
    "discovery_frustrations": (
        "what are the top frustrations with recommendations",
        "what recommendation complaints appear most",
        "why are users unhappy with recommendations",
        "what frustrates spotify users",
        "what are the top frustrations",
        "what discovery frustrations do users report",
        "what frustrates users about music discovery",
    ),
    "user_segments": (
        "which user segments experience discovery challenges",
        "which listeners have discovery problems",
        "which users struggle most",
        "who faces discovery issues",
    ),
    "repetitive_listening_behavior": (
        "why do users hear the same songs repeatedly",
        "why do users hear the same songs",
        "what causes repetitive listening behavior",
        "what causes repetitive listening",
        "why are spotify recommendations repetitive",
        "why are recommendations repetitive",
        "why does spotify repeat songs",
    ),
    "unmet_needs": (
        "what unmet needs emerge consistently across reviews",
        "what user needs are not addressed",
        "what do users want from discovery",
        "what unmet needs emerge",
        "what opportunities exist",
    ),
    "music_discovery_challenges": (
        "why do users struggle to discover new music",
        "why is music discovery difficult",
        "what blocks music discovery",
        "why can't users find new artists",
        "why cant users find new artists",
    ),
    "playlist_dependency": (
        "why do users rely heavily on playlists",
        "how dependent are users on discover weekly",
        "why do users depend on playlists",
    ),
    "product_opportunities": (
        "what product improvements should spotify prioritize",
        "what should the product team focus on",
        "what should spotify build",
    ),
    "ai_assisted_discovery": (
        "what opportunities exist for ai-powered discovery",
        "how could ai improve music discovery",
        "ai-powered discovery opportunities",
    ),
    "recommendation_quality": (
        "why are recommendations irrelevant",
        "what drives poor recommendation quality",
        "recommendation quality problems",
    ),
    "discovery_journeys": (
        "how do users discover new music on spotify",
        "what does the discovery journey look like",
        "discovery journey on spotify",
    ),
}

# Business / corporate topics — always rejected before cluster scoring.
_BUSINESS_BLOCKLIST = (
    "revenue",
    "founder",
    "founded",
    "who founded",
    "stock",
    "stock price",
    "valuation",
    "market share",
    "company history",
    "ceo",
    "chief executive",
    "headquarters",
    "earnings",
    "profit",
    "ipo",
    "market cap",
    "share price",
    "subsidiary",
    "acquisition",
    "net worth",
    "employees count",
    "how many employees",
)

_OUT_OF_SCOPE_MARKERS = (
    "weather",
    "bitcoin",
    "crypto",
    "politics",
    "recipe",
    "cooking",
    "football",
    "basketball",
    "soccer",
    "movie",
    "netflix video",
    "instagram photo",
)

# Discovery-research vocabulary — brand name alone (e.g. "Spotify") is insufficient.
_DISCOVERY_INTENT_KEYWORDS = frozenset({
    "discover", "discovery", "playlist", "recommend", "recommendation",
    "algorithm", "listen", "listening", "repetitive", "repeat", "segment",
    "frustration", "frustrated", "unmet", "cause", "explore", "exploration",
    "journey", "opportunity", "review", "reviews", "user", "users",
    "artist", "artists", "song", "songs", "genre", "shuffle", "autoplay",
    "premium", "discover weekly", "release radar", "daily mix",
    "personalization", "ai-powered", "ai-assisted",
})

_STOPWORDS = frozenset({
    "what", "when", "where", "which", "who", "why", "how", "does", "do",
    "the", "and", "for", "with", "about", "from", "that", "this", "are",
    "is", "users", "user", "spotify", "music", "was", "were", "have", "has",
})


def _tokens(text: str) -> set[str]:
    return {
        t for t in re.split(r"\W+", text.lower())
        if len(t) > 2 and t not in _STOPWORDS
    }


def _fuzzy_ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _token_overlap(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


def _normalize_question(text: str) -> str:
    q = (text or "").lower().strip()
    q = q.rstrip("?.!")
    q = re.sub(r"\s+", " ", q)
    return q


def _is_business_question(question: str) -> bool:
    q = question.lower().strip()
    return any(term in q for term in _BUSINESS_BLOCKLIST)


def _is_general_out_of_scope(question: str) -> bool:
    q = question.lower().strip()
    return any(marker in q for marker in _OUT_OF_SCOPE_MARKERS)


def _has_discovery_intent(question: str) -> bool:
    q = question.lower().strip()
    if any(kw in q for kw in _DISCOVERY_INTENT_KEYWORDS):
        return True
    for spec in _CATEGORY_SIGNALS.values():
        if any(pattern in q for pattern in spec["patterns"]):
            return True
    return False


def _cluster_confidence(question: str, spec: dict[str, Any]) -> float:
    """Return a normalized 0–1 confidence for one research category."""
    q_lower = question.lower().strip()

    pattern_hits = [p for p in spec["patterns"] if p in q_lower]
    if pattern_hits:
        pattern_conf = min(1.0, sum(0.32 + len(p) * 0.006 for p in pattern_hits))
    else:
        pattern_conf = 0.0

    example_conf = 0.0
    for example in spec.get("examples", ()):
        overlap = _token_overlap(question, example)
        fuzzy = _fuzzy_ratio(question, example)
        if overlap >= 0.25:
            sim = max(overlap, fuzzy * 0.85)
        elif overlap > 0:
            sim = overlap * 0.55 + fuzzy * 0.12
        else:
            # Do not map unknown questions via brand-name fuzzy similarity alone.
            sim = fuzzy * 0.05
        example_conf = max(example_conf, sim)

    if pattern_conf >= 0.35:
        return min(1.0, pattern_conf * 0.78 + example_conf * 0.22)
    if example_conf >= 0.45:
        return min(1.0, example_conf * 0.82 + pattern_conf * 0.18)
    return min(1.0, pattern_conf * 0.45 + example_conf * 0.55)


def score_all_clusters(question: str) -> dict[str, float]:
    """Return normalized confidence (0–1) for every research category."""
    return {
        cat_id: _cluster_confidence(question, spec)
        for cat_id, spec in _CATEGORY_SIGNALS.items()
    }


def _alias_match_score(question: str, alias: str) -> float:
    q = _normalize_question(question)
    alias_norm = _normalize_question(alias)
    if not q or not alias_norm:
        return 0.0
    if alias_norm in q or q in alias_norm:
        return min(1.0, 0.92 + len(alias_norm) * 0.002)
    overlap = _token_overlap(q, alias_norm)
    fuzzy = _fuzzy_ratio(q, alias_norm)
    if overlap >= 0.45:
        return min(1.0, max(overlap, fuzzy * 0.9))
    if overlap >= 0.25:
        return min(1.0, overlap * 0.85 + fuzzy * 0.35)
    return max(overlap, fuzzy * 0.45)


def match_semantic_alias(question: str) -> tuple[str | None, float]:
    """Return the best matching category via validated semantic aliases."""
    best_cat: str | None = None
    best_score = 0.0
    best_alias_len = 0

    for cat_id, aliases in _SEMANTIC_ALIASES.items():
        for alias in aliases:
            score = _alias_match_score(question, alias)
            alias_len = len(_normalize_question(alias))
            if score > best_score or (
                score >= MIN_ALIAS_CONFIDENCE
                and abs(score - best_score) < 0.02
                and alias_len > best_alias_len
            ):
                if score >= MIN_ALIAS_CONFIDENCE or score > best_score:
                    best_score = score
                    best_cat = cat_id
                    best_alias_len = alias_len

    if best_cat is None or best_score < MIN_ALIAS_CONFIDENCE:
        return None, best_score
    return best_cat, best_score


def _log_classification_debug(
    question: str,
    top_cluster: str | None,
    confidence: float,
    accepted: bool,
    match_source: str = "cluster",
) -> None:
    print(
        json.dumps(
            {
                "question": question,
                "topCluster": top_cluster,
                "confidence": round(confidence, 4),
                "accepted": accepted,
                "matchSource": match_source,
            },
            ensure_ascii=True,
        )
    )


def classify_query(question: str) -> tuple[str | None, float, str]:
    """Return ``(category_id, confidence, human_label)``.

    ``category_id`` is ``None`` when the question is outside research scope or
    when the highest cluster confidence is below ``MIN_CONFIDENCE``.
    """
    q = (question or "").strip()
    if not q:
        _log_classification_debug(q, None, 0.0, False)
        return None, 0.0, ""

    if _is_business_question(q) or _is_general_out_of_scope(q):
        _log_classification_debug(q, None, 0.0, False, "blocked")
        return None, 0.0, ""

    alias_cat, alias_conf = match_semantic_alias(q)
    if alias_cat:
        _log_classification_debug(q, alias_cat, alias_conf, True, "alias")
        return alias_cat, alias_conf, CATEGORY_LABELS[alias_cat]

    if not _has_discovery_intent(q):
        _log_classification_debug(q, None, 0.0, False, "no_intent")
        return None, 0.0, ""

    cluster_scores = score_all_clusters(q)
    if not cluster_scores:
        _log_classification_debug(q, None, 0.0, False, "cluster")
        return None, 0.0, ""

    best_cat = max(cluster_scores, key=cluster_scores.get)  # type: ignore[arg-type]
    best_conf = cluster_scores[best_cat]
    accepted = best_conf >= MIN_CONFIDENCE

    _log_classification_debug(q, best_cat if accepted else None, best_conf, accepted, "cluster")

    if not accepted:
        return None, best_conf, ""

    return best_cat, best_conf, CATEGORY_LABELS[best_cat]


OUT_OF_SCOPE_MESSAGE = (
    "This question falls outside the scope of the Spotify music discovery "
    "research dataset. This system only analyzes:\n"
    "• music discovery behavior\n"
    "• repetitive listening\n"
    "• user frustrations\n"
    "• unmet needs\n"
    "• root causes\n"
    "• user segments\n"
    "• product opportunities"
)


__all__ = [
    "CATEGORY_LABELS",
    "MIN_CONFIDENCE",
    "MIN_ALIAS_CONFIDENCE",
    "OUT_OF_SCOPE_MESSAGE",
    "classify_query",
    "match_semantic_alias",
    "score_all_clusters",
]
