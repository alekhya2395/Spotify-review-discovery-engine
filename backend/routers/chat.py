"""Groq-grounded chat — every answer is tailored to the user's question.

Output is an 8-section markdown structure where each section is included only
when the indexed review data supports it:

1. Summary             (always)
2. Evidence            (counts/%s computed from the dataset — never invented)
3. Key Pain Points     (when matched reviews carry pain categories)
4. Root Causes         (when matched reviews carry unmet needs / themes)
5. Affected User Segments (when segment distribution is meaningful)
6. Unmet Needs         (when reviews/themes call out unmet expectations)
7. Product Focus Areas (when the question asks about direction or opportunity)
8. Recommended Actions (always for actionable questions)
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

sys.path.append(str(Path(__file__).resolve().parents[2]))

from groq_env import groq_api_key, groq_chat_model  # noqa: E402
from rag import build_review_context  # noqa: E402
from discovery_insights import compute_discovery_insights  # noqa: E402
from root_causes import compute_root_causes  # noqa: E402
from user_segments import compute_user_segments  # noqa: E402
from unmet_need_inference import (  # noqa: E402
    DISCOVERY_FOCUSED_NEEDS,
    NON_UNMET_NEED_LABELS,
    strategic_rewrite,
)
from confidence import (  # noqa: E402
    confidence_markdown_lines,
    enrich_finding,
    source_counts_for_pain_category,
)
from format_labels import (  # noqa: E402
    FOCUS_AREA_BY_TOPIC,
    PAIN_INSIGHT,
    actions_for_intent,
    detect_question_intent,
    detect_topic,
    format_pain,
    format_segment,
    is_noisy_theme,
    pain_allowed_for_topic,
    pain_lines,
    score_review_relevance,
    summary_for_intent,
)

router = APIRouter()
logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = groq_chat_model()
GROQ_FALLBACK_MODEL = os.getenv("GROQ_CHAT_FALLBACK_MODEL", "llama-3.1-8b-instant")
GROQ_TIMEOUT_SECONDS = float(os.getenv("GROQ_CHAT_TIMEOUT", "45"))
GROQ_TEMPERATURE = float(os.getenv("GROQ_CHAT_TEMPERATURE", "0"))

# Set CHAT_STABLE_MODE=true (default) for deterministic, evaluation-ready answers.
# Set CHAT_STABLE_MODE=false to allow Groq paraphrasing (answers may vary slightly).
CHAT_STABLE_MODE = os.getenv("CHAT_STABLE_MODE", "true").lower() not in ("0", "false", "no")

MAX_HISTORY_TURNS = 4
MAX_HISTORY_CHARS = 600

SECTION_ORDER = [
    "Summary",
    "Evidence",
    "Key Pain Points",
    "Root Causes",
    "Affected User Segments",
    "Unmet Needs",
    "Product Focus Areas",
    "Recommended Actions",
]

REQUIRED_SECTIONS = {"Summary"}

SECTION_ALIASES: dict[str, str] = {
    "summary": "Summary",
    "executive summary": "Summary",
    "overview": "Summary",
    "tldr": "Summary",
    "evidence": "Evidence",
    "supporting evidence": "Evidence",
    "data points": "Evidence",
    "data evidence": "Evidence",
    "key pain points": "Key Pain Points",
    "pain points": "Key Pain Points",
    "key findings": "Key Pain Points",
    "main pain points": "Key Pain Points",
    "top complaints": "Key Pain Points",
    "root causes": "Root Causes",
    "root cause": "Root Causes",
    "underlying causes": "Root Causes",
    "drivers": "Root Causes",
    "why it happens": "Root Causes",
    "affected user segments": "Affected User Segments",
    "user segments": "Affected User Segments",
    "affected segments": "Affected User Segments",
    "segments affected": "Affected User Segments",
    "who is affected": "Affected User Segments",
    "unmet needs": "Unmet Needs",
    "user needs": "Unmet Needs",
    "what users want": "Unmet Needs",
    "what users need": "Unmet Needs",
    "missing needs": "Unmet Needs",
    "product focus areas": "Product Focus Areas",
    "focus areas": "Product Focus Areas",
    "product priorities": "Product Focus Areas",
    "strategic focus": "Product Focus Areas",
    "where to focus": "Product Focus Areas",
    "recommended actions": "Recommended Actions",
    "recommendations": "Recommended Actions",
    "next steps": "Recommended Actions",
    "actions": "Recommended Actions",
    "suggested actions": "Recommended Actions",
    "action items": "Recommended Actions",
}

# Map question intents → sections that are most relevant. Other sections are
# emitted only when the review data clearly supports them.
INTENT_SECTIONS: dict[str, tuple[str, ...]] = {
    "why_cause": (
        "Summary", "Evidence", "Key Pain Points", "Root Causes",
        "Recommended Actions",
    ),
    "opportunity": (
        "Summary", "Evidence", "Product Focus Areas", "Unmet Needs",
        "Recommended Actions",
    ),
    "pain_list": (
        "Summary", "Evidence", "Key Pain Points", "Affected User Segments",
        "Recommended Actions",
    ),
    "listening_goals": (
        "Summary", "Evidence", "Unmet Needs", "Affected User Segments",
        "Product Focus Areas",
    ),
    "segment_question": (
        "Summary", "Evidence", "Affected User Segments", "Key Pain Points",
        "Recommended Actions",
    ),
    "general": (
        "Summary", "Evidence", "Key Pain Points", "Root Causes",
        "Affected User Segments", "Unmet Needs", "Product Focus Areas",
        "Recommended Actions",
    ),
}

SYSTEM_PROMPT = """You are the Spotify Review Discovery Engine — a senior product analyst answering questions about Spotify user feedback.

You answer using ONLY the review context provided. Tone: clear, professional, executive-ready.

CRITICAL RULES
1. Tailor every answer to the EXACT question. Different questions must produce substantially different answers.
2. Before writing, identify the user's intent: cause, opportunity, complaint, segment-question, behavior, etc. The answer must serve that intent.
3. Only include sections that are SUPPORTED by the supplied review data. Omit sections that the data does not back up.
4. Never invent numbers. Numbers, counts, and percentages may only come from `dataset_stats` or `evidence` in the CONTEXT.
5. Never copy verbatim user quotes or review IDs. Paraphrase patterns instead.
6. Each section must add new information. Do not repeat the same point across Summary, Pain Points, Causes, Focus Areas, and Actions.

OUTPUT FORMAT (markdown — use `## Header` for each section)

## Summary
2–3 sentences that directly answer the question. State the finding as a product insight, not a description of the dataset.

## Evidence
Use the FULL analyzed dataset as the denominator — never the small "matched_reviews" subset.

Open the section with two header lines (NOT bullets):

**Total Reviews Analyzed:** `<evidence.total_reviews>`

**Discovery-Related Reviews:** `<evidence.discovery_related.count>` (`<evidence.discovery_related.share>`)

Then list 4–8 bullets, each a SPECIFIC finding with a meaningful sample size. Use this exact wording pattern:
- `- **{label}** — {count} reviews ({percent} of {pool}) {prose}.`
  Immediately follow with two indented sub-bullets from `evidence.findings[].confidence`:
  `  - **Confidence:** High|Medium|Low`
  `  - **Supported by:** {confidence_support}`

Pull the counts, percentages, confidence, and support lines from `evidence.findings` (already pre-ranked) plus `evidence.discovery_insights` / `evidence.root_causes` / `evidence.user_segments`. NEVER write things like "Supporting Reviews: 5", "Matched reviews: 14", or any number below ~10 that would look statistically weak. NEVER invent numbers; if the context only gives a small denominator for a finding, omit that finding.

If no findings reach a meaningful sample size, OMIT the Evidence section entirely.

## Key Pain Points
3–5 bullets. Each bullet is a specific user complaint RELEVANT to the question.
Format:
- `- **<Pain Category>**: <one sentence>.`
  Then add confidence sub-bullets when `pain_categories[].confidence` is present:
  `  - **Confidence:** High|Medium|Low`
  `  - **Supported by:** {confidence_support}`

## Root Causes
3–5 bullets explaining WHY the pain points happen, drawn from review unmet_need patterns and themes.
Format:
- `- **<Cause label>**: <one sentence>.`
  Then add confidence sub-bullets when `root_causes[].confidence` is present:
  `  - **Confidence:** High|Medium|Low`
  `  - **Supported by:** {confidence_support}`

## Affected User Segments
3–5 bullets naming user segments most impacted. Use segments named in the context. Add a % only if it appears in `dataset_stats.segments` or `evidence`.

## Unmet Needs
3–5 bullets describing what users are trying to achieve but currently cannot. Paraphrase `unmet_need` patterns.

## Product Focus Areas
3–5 bullets — strategic product directions Spotify should prioritize. Distinct from the pain points above.

## Recommended Actions
3–5 bullets — concrete next steps for the Spotify product team. Specific, practical, distinct from focus areas.

SECTION SELECTION
- ALWAYS include `## Summary`.
- Omit any section without supporting data in CONTEXT.
- "Why / cause / struggle" questions → emphasize Evidence, Key Pain Points, Root Causes, Recommended Actions.
- "Opportunity / improve / how should we" questions → emphasize Unmet Needs, Product Focus Areas, Recommended Actions.
- "Who / which users / which segment" questions → emphasize Affected User Segments, Key Pain Points.
- "What pain points / complaints / frustrations" questions → emphasize Evidence, Key Pain Points, Affected User Segments.

Length: 250–500 words total. No preamble, no closing remark — output the markdown sections only.
"""


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=2000)
    history: list[dict] | None = None


class ChatResponse(BaseModel):
    answer: str
    grounding_size_chars: int
    matched_reviews: int = 0


# ---------------------------------------------------------------------------
# Intent detection — maps questions to specific topic areas
# ---------------------------------------------------------------------------

INTENTS: dict[str, tuple[str, ...]] = {
    "discovery_struggle": (
        "why do users struggle", "struggle to discover", "hard to find new",
        "difficulty discovering", "trouble finding", "can't find new music",
        "struggle with discovery",
    ),
    "recommendation_frustration": (
        "frustration", "frustrated", "common complaints about recommend",
        "problems with recommend", "issues with recommend", "recommendation quality",
        "what frustrates", "most common frustration",
    ),
    "listening_behavior": (
        "listening behavior", "listening habits", "listening pattern",
        "what are users trying to achieve", "listening goals", "how do users listen",
        "what listening", "music consumption",
    ),
    "repetition": (
        "repeat", "repetitive", "repeatedly", "same content", "same songs", "same artists",
        "same music", "loop", "stuck listening", "causes users to repeatedly",
        "why do users listen to the same", "listen to the same", "over and over",
        "monoton", "again and again",
    ),
    "segments": (
        "segment", "user type", "different users", "which users",
        "user groups", "demographic", "persona", "different challenges",
        "who experiences", "which user segment",
    ),
    "unmet_needs": (
        "unmet need", "what do users want", "what users need", "consistently emerge",
        "what's missing", "gaps", "expectations", "what users ask for",
    ),
    "pricing": (
        "price", "pricing", "premium", "subscription", "expensive", "cost",
        "free tier", "ad supported", "family plan", "student plan",
    ),
    "ui_ux": (
        "ui", "ux", "interface", "design", "navigation", "usability",
        "hard to use", "confusing",
    ),
    "performance": (
        "crash", "bug", "slow", "lag", "performance", "freeze", "stability",
    ),
    "social": (
        "social", "share", "friend", "collaborative", "together",
    ),
}


def _detect_intent(question: str) -> str:
    q = question.lower().strip()
    best_intent = "general"
    best_score = 0
    for intent, keywords in INTENTS.items():
        score = sum(3 + len(kw) for kw in keywords if kw in q)
        if score > best_score:
            best_score = score
            best_intent = intent
    return best_intent


# ---------------------------------------------------------------------------
# Fallback answers — each intent produces a DIFFERENT answer
# ---------------------------------------------------------------------------

FALLBACK_ANSWERS: dict[str, str] = {
    "discovery_struggle": """**Summary**

Users struggle to discover new music primarily because the algorithm heavily favors familiar artists and genres they already listen to. The recommendation system creates a comfort bubble that becomes increasingly difficult to break out of, and the limited discovery surfaces beyond Discover Weekly offer few alternative pathways to unfamiliar content.

**Key pain points**

- **Algorithm echo chamber**: The recommendation engine reinforces existing listening habits rather than introducing genuinely new or unfamiliar artists
- **Limited discovery surfaces**: Beyond Discover Weekly and Release Radar, users have few dedicated pathways to explore music outside their established preferences
- **Genre lock-in**: Once a user establishes a listening pattern, the algorithm struggles to suggest content from entirely different genres or styles
- **Lack of contextual discovery**: Users want music discovery tied to moods, activities, or life moments — not just listening history

**Product focus areas**

- **Discovery diversity controls**: Build explicit user-facing controls that let listeners indicate how adventurous they want their recommendations to be
- **New artist surfaces**: Create dedicated spaces for emerging artists and genres the user has never explored
- **Serendipity mechanisms**: Introduce intentional randomness and cross-genre bridges in autoplay and radio
- **Social discovery paths**: Leverage what friends and similar listeners are discovering as a recommendation signal

**Recommended actions**

- Introduce a "discovery intensity" slider that lets users control how much novelty they want in algorithmic playlists
- Launch a dedicated "Explore" tab focused exclusively on content outside the user's established taste profile
- Add "break the loop" prompts that appear when the algorithm detects repetitive listening patterns
- Test curator-driven discovery feeds as an alternative to purely algorithmic recommendations""",

    "recommendation_frustration": """**Summary**

The most common frustrations with Spotify's recommendation system center around repetitiveness and staleness. Users consistently report that recommendations cycle through the same small pool of artists, that Discover Weekly loses freshness over time, and that the algorithm fails to distinguish between casual listening and genuine preference signals.

**Key pain points**

- **Repetitive suggestions**: The same artists and tracks appear across multiple recommendation surfaces, creating a feeling of staleness
- **Signal misinterpretation**: A single play or accidental listen permanently skews recommendations, with no easy way to correct the algorithm
- **Discover Weekly decay**: Users report that Discover Weekly starts strong but becomes repetitive after several months of use
- **One-dimensional profiling**: Recommendations fail to account for different listening contexts — working out, studying, relaxing, or socializing each require different music

**Product focus areas**

- **Algorithmic freshness**: Implement decay mechanisms that rotate out previously recommended content and enforce novelty quotas
- **Intent-aware recommendations**: Distinguish between active discovery, background listening, and mood-based sessions to provide contextually appropriate suggestions
- **Feedback correction**: Make it easier for users to tell the algorithm when a recommendation was wrong without fully resetting their profile
- **Multi-taste modeling**: Build separate taste profiles for different listening moods rather than one averaged profile

**Recommended actions**

- Add visible "not interested" and "more like this" controls on every recommendation surface
- Implement a freshness constraint that prevents the same artist from appearing in recommendations more than once per week
- Build context detection that adjusts recommendations based on time of day, activity, and listening device
- Create a "recommendation reset" option for specific genres or artists without wiping the entire profile""",

    "listening_behavior": """**Summary**

Users exhibit diverse listening behaviors that Spotify's current system inadequately supports. The primary listening goals range from active music discovery and mood-based selection to passive background listening and social sharing — each requiring fundamentally different algorithmic approaches and interface affordances.

**Key pain points**

- **Mode mismatch**: The app treats all listening equally, whether a user is actively exploring or passively having background music
- **Playlist management friction**: Creating, organizing, and maintaining playlists for different moods and activities is cumbersome
- **Session continuity gaps**: When users finish a playlist or album, autoplay often disrupts the established mood or energy level
- **Cross-context confusion**: Listening to a workout playlist pollutes relaxation recommendations and vice versa

**Product focus areas**

- **Listening mode detection**: Automatically detect whether users are in active discovery, passive listening, or focused work mode and adapt the experience
- **Smart session management**: Improve autoplay logic to maintain energy, mood, and genre consistency when content ends
- **Activity-based organization**: Provide better tools for organizing music by activity, mood, and context rather than just playlists
- **Separation of listening contexts**: Allow users to maintain distinct taste profiles for different listening situations

**Recommended actions**

- Implement listening "modes" that users can explicitly set (discover, focus, workout, sleep) with tailored algorithmic behavior for each
- Build smarter autoplay that analyzes the mood and tempo arc of what was played before suggesting next tracks
- Add automatic playlist organization by detected listening context
- Test "session history" that lets users revisit and save music from specific listening sessions""",

    "repetition": """**Summary**

Users fall into repetitive listening patterns because the algorithm optimizes for engagement (replaying known favorites) over exploration. The comfort of familiar music combined with insufficient prompts to explore creates a self-reinforcing loop where the algorithm keeps serving what it already knows the user will accept.

**Key pain points**

- **Algorithmic reinforcement loop**: The system interprets repeated plays as strong preference signals, which leads to even more of the same content being recommended
- **Comfort over exploration**: Users default to familiar music when no compelling alternative is presented, and the app rarely challenges this behavior
- **Autoplay repetitiveness**: When users don't actively choose music, autoplay tends toward safe, already-heard tracks rather than introducing new content
- **No variety awareness**: The system lacks a mechanism to detect and break monotonous listening patterns proactively

**Product focus areas**

- **Loop detection and intervention**: Build systems that identify when users are stuck in repetitive patterns and offer gentle nudges toward new content
- **Balanced optimization**: Shift recommendation objectives from pure engagement (replays) toward a blend of satisfaction and discovery
- **Autoplay diversity**: Increase the novelty injection in autoplay and radio sessions with configurable intensity
- **Listening history awareness**: Use temporal patterns to identify when users might be open to exploring versus when they want comfort

**Recommended actions**

- Add "break the loop" notifications or playlist suggestions when repetitive patterns are detected
- Redesign autoplay to gradually introduce unfamiliar tracks mixed with familiar ones, increasing novelty over time
- Implement a "listening diversity score" visible to users that encourages exploration
- Create time-based triggers that suggest new music after a threshold of repeated content consumption""",

    "segments": """**Summary**

Different user segments experience distinct discovery challenges based on their listening style, subscription tier, and engagement level. Power listeners face algorithm fatigue and echo chambers, casual users struggle with limited onboarding, free-tier users are frustrated by ad interruptions during discovery, and niche-genre enthusiasts find the mainstream-biased algorithm particularly ineffective.

**Key pain points**

- **Power listeners vs. casual users**: Heavy users exhaust recommendations quickly and need deeper catalogs, while casual users need simpler, curated entry points
- **Free vs. Premium disparity**: Free-tier users face ad interruptions that break the discovery flow and shuffle-only mode prevents intentional exploration
- **Niche genre enthusiasts**: Users with specialized taste profiles (jazz, classical, regional music) find mainstream-optimized algorithms especially poor at serving their needs
- **New users vs. long-term subscribers**: New users lack enough data for personalization, while long-term users feel locked into stale taste profiles

**Product focus areas**

- **Segment-specific onboarding**: Tailor the initial experience based on detected listening style rather than one-size-fits-all
- **Depth for power users**: Provide advanced discovery tools and deeper algorithmic exploration for heavy listeners
- **Free-tier discovery protection**: Reduce friction in the discovery experience for non-paying users to support eventual conversion
- **Genre-specialist algorithms**: Develop or tune recommendation models for underserved genre communities

**Recommended actions**

- Build listening-style segmentation into the recommendation engine and adapt surfaces per segment
- Create a "deep cuts" mode for power listeners that specifically targets less-played catalog
- Design a lighter ad experience specifically during active discovery sessions on the free tier
- Develop genre-specialist recommendation tracks for communities poorly served by the general algorithm""",

    "unmet_needs": """**Summary**

The most consistently emerging unmet needs across user reviews center on meaningful personalization control, diverse discovery pathways, and transparent algorithmic behavior. Users repeatedly express wanting more agency over how the algorithm shapes their experience, rather than being passive recipients of automated recommendations.

**Key pain points**

- **Lack of user control over algorithms**: Users want to influence, adjust, and override what the recommendation engine does — not just accept its output
- **No dedicated exploration experience**: There is no space in the app designed purely for discovering unfamiliar music without algorithmic bias from past behavior
- **Poor feedback mechanisms**: Users cannot easily tell the system what went wrong with a recommendation or what direction they want to go
- **Missing social discovery features**: Users want to discover music through trusted human connections (friends, curators, communities) rather than algorithms alone

**Product focus areas**

- **Algorithmic transparency and control**: Give users visible levers to tune their recommendation experience and understand why content was suggested
- **Dedicated discovery space**: Build a distinct section of the app focused on exploration that operates independently from the main recommendation feed
- **Rich feedback loops**: Create intuitive ways for users to correct, refine, and direct the algorithm beyond simple like/dislike
- **Human-powered discovery**: Invest in curator, editorial, and social discovery features alongside algorithmic approaches

**Recommended actions**

- Design a "why was this recommended" explainability feature with actionable controls
- Launch a dedicated Explore section with curated discovery pathways independent of personal history
- Implement multi-signal feedback (mood, energy, context) beyond binary like/dislike
- Build community-driven discovery through taste-matched groups and trusted curator networks""",

    "pricing": """**Summary**

Pricing frustrations concentrate around perceived poor value on the Premium tier relative to competitors, confusing family and student plan policies, and an excessively aggressive ad experience on the free tier that pushes users away rather than converting them.

**Key pain points**

- **Premium value perception**: Users question whether Premium offers enough beyond ad removal to justify the monthly cost
- **Ad overload on free tier**: The frequency and length of ads is perceived as punitive rather than a natural trade-off, driving users to competitors
- **Plan complexity**: Family plan verification, student eligibility requirements, and tier differences create friction
- **Price sensitivity in emerging markets**: Users in developing countries find global pricing misaligned with local purchasing power

**Product focus areas**

- **Premium differentiation**: Strengthen exclusive features (audio quality, offline, discovery tools) to justify the subscription cost
- **Free-tier ad balance**: Reduce perceived hostility of the ad experience while maintaining revenue
- **Plan simplification**: Streamline family and student verification processes and clarify tier benefits
- **Localized value propositions**: Adapt pricing and feature bundles to regional economic contexts

**Recommended actions**

- Conduct value-perception research to identify which Premium features users consider most worth paying for
- Test reduced ad frequency with longer individual ads to improve the free-tier experience without revenue loss
- Simplify plan enrollment and verification workflows
- Develop market-specific pricing tiers for regions with high churn due to cost""",

    "ui_ux": """**Summary**

UI and UX frustrations revolve around navigation complexity, difficulty managing large music libraries, unintuitive playlist organization, and frequent changes to familiar interface patterns that disrupt established user workflows.

**Key pain points**

- **Navigation depth**: Key features are buried too deep in menus, requiring too many taps to reach frequently used functions
- **Library management**: Organizing saved music, albums, and playlists becomes increasingly painful as libraries grow
- **Interface instability**: Frequent redesigns and feature relocations frustrate users who had learned previous patterns
- **Discovery UX**: The path from hearing a recommendation to exploring the artist and saving content involves too much friction

**Product focus areas**

- **Information architecture**: Flatten navigation and bring frequently-used actions to more accessible positions
- **Library scalability**: Design library management tools that work well at scale — filtering, sorting, bulk operations
- **Change management**: Implement UI changes more gradually and provide clear migration paths for users
- **Exploration flow**: Reduce the number of steps between discovery and action (save, playlist add, artist dive)

**Recommended actions**

- Run usability audits on the top user flows and reduce tap-count for common actions
- Build power-user library tools (smart playlists, bulk edit, advanced search within library)
- Adopt a more gradual rollout approach for major UI changes with opt-in periods
- Streamline the "discover to save" flow to require fewer interactions""",

    "performance": """**Summary**

Performance and stability concerns focus on app crashes during playback, slow loading times for library and search, Bluetooth connectivity issues, and battery drain — all of which erode trust in the core listening experience.

**Key pain points**

- **Playback interruptions**: Unexpected pauses, skips, and crashes during music playback undermine the fundamental value proposition
- **Slow load times**: Library, search results, and playlist loading feel sluggish, especially on older devices or slower connections
- **Bluetooth instability**: Connection drops and audio quality degradation over Bluetooth are a persistent complaint
- **Battery and resource consumption**: The app is perceived as resource-heavy relative to its function

**Product focus areas**

- **Playback reliability**: Invest in playback engine stability as the highest-priority technical concern
- **Performance optimization**: Reduce memory and loading times, especially for large libraries
- **Bluetooth stack improvements**: Improve codec negotiation and connection recovery for wireless audio
- **Resource efficiency**: Optimize background processes and caching to reduce battery impact

**Recommended actions**

- Establish playback reliability as a top-line engineering metric with zero-tolerance for regression
- Profile and optimize the library and search loading paths for low-end devices
- Implement better Bluetooth reconnection logic and codec fallback handling
- Reduce background activity and optimize caching strategies for battery efficiency""",

    "social": """**Summary**

Users consistently express wanting richer social features that enable collaborative listening, shared discovery, and music-based connection with friends. The current social experience feels minimal compared to the richness of the music platform itself.

**Key pain points**

- **Limited collaborative features**: Group playlists and shared listening sessions feel basic and disconnected from the core experience
- **No social discovery feed**: Users cannot easily see what friends are discovering or find music through social connections
- **Sharing friction**: Sharing music to external platforms or within Spotify involves too many steps
- **Community absence**: There is no in-app community or discussion space around music, artists, or genres

**Product focus areas**

- **Collaborative listening**: Expand real-time and asynchronous shared listening experiences
- **Social discovery**: Build a feed or surface showing friend activity, shared playlists, and social recommendations
- **Frictionless sharing**: Make sharing music within and outside the app effortless
- **Community spaces**: Create spaces for discussion and connection around shared musical interests

**Recommended actions**

- Enhance collaborative playlist features with real-time activity indicators and voting
- Launch a social discovery feed showing what friends are saving and discovering
- Implement one-tap sharing to stories and messages across platforms
- Test community spaces around genres, moods, or local music scenes""",

    "general": """**Summary**

Analysis of Spotify user feedback reveals that the most significant areas of concern span across music discovery limitations, recommendation repetitiveness, and insufficient user control over the algorithmic experience. Users want a more personalized, diverse, and transparent music platform.

**Key pain points**

- **Discovery limitations**: Users find it difficult to break out of their established listening patterns and discover genuinely new music
- **Recommendation staleness**: Algorithmic suggestions become repetitive over time, cycling through the same pool of artists
- **Lack of user control**: Users feel they have insufficient ability to influence or correct how the algorithm shapes their experience
- **Interface friction**: Common actions require too many steps, and frequent UI changes disrupt established workflows

**Product focus areas**

- **Discovery innovation**: Create multiple pathways to new music that don't rely solely on algorithmic history
- **Recommendation freshness**: Implement diversity and novelty constraints in the recommendation engine
- **User empowerment**: Give users visible controls over algorithmic behavior and personalization
- **Experience polish**: Reduce friction in core flows and maintain UI consistency

**Recommended actions**

- Prioritize building dedicated discovery experiences separate from the main recommendation feed
- Implement freshness constraints that prevent algorithmic staleness
- Design user-facing controls that provide transparency and agency over recommendations
- Conduct systematic UX audits on the most-used flows to reduce unnecessary friction""",
}


# ---------------------------------------------------------------------------
# Output sanitizer — removes all numbers, counts, quotes from answers
# ---------------------------------------------------------------------------

# IDs and verbatim quotes are stripped; numeric evidence is preserved so the
# Evidence section can carry real counts and percentages from the dataset.
_ID_PATTERNS = [
    re.compile(r"(?:app_store|play_store|reddit|social_media|community_forum):[^\s,;]+", re.IGNORECASE),
    re.compile(r"\breview[_\s-]?id[:\s]+\S+", re.IGNORECASE),
]

_QUOTE_PATTERNS = [
    re.compile(r'^>\s*".*"$', re.MULTILINE),
    re.compile(r"^>\s*—.*$", re.MULTILINE),
    re.compile(r'^"[^"]{40,}"$', re.MULTILINE),
]


def _strip_ids_and_quotes(text: str) -> str:
    """Remove review IDs and standalone verbatim quotes — keep evidence numbers."""
    for pat in _ID_PATTERNS:
        text = pat.sub("", text)
    for pat in _QUOTE_PATTERNS:
        text = pat.sub("", text)
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r"[^\S\n]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# Legacy alias kept for any internal callers; behavior switched to preserve numbers.
_strip_numbers_and_quotes = _strip_ids_and_quotes


# ---------------------------------------------------------------------------
# Section normalizer
# ---------------------------------------------------------------------------


_HEADER_PATTERNS = (
    re.compile(r"^\s*#{1,6}\s+(.+?)\s*$"),                   # "## Header"
    re.compile(r"^\s*\*\*([^*]+?)\*\*\s*:?\s*$"),            # "**Header**"
    re.compile(r"^\s*\*\*([^*]+?)\*\*\s*[:\-\u2014]\s*(.+)$"),  # "**Header**: inline"
)


def _match_header(line: str) -> tuple[str | None, str]:
    """Return (canonical_section, inline_content) if line is a known header."""
    for pat in _HEADER_PATTERNS:
        m = pat.match(line)
        if not m:
            continue
        header_raw = m.group(1)
        inline = m.group(2).strip() if m.lastindex and m.lastindex >= 2 else ""
        key = header_raw.strip().lower().rstrip(":").strip("*").strip()
        # Drop leading numbering like "1. Summary" or "1) Summary"
        key = re.sub(r"^\d+[\.\)]\s*", "", key)
        canonical = SECTION_ALIASES.get(key)
        if canonical:
            return canonical, inline
    return None, ""


def _split_into_sections(text: str) -> dict[str, str]:
    lines = text.splitlines()
    sections: dict[str, list[str]] = {}
    current: str | None = None
    buffer: list[str] = []

    def flush():
        nonlocal buffer
        if current and buffer:
            existing = sections.get(current, [])
            existing.extend(buffer)
            sections[current] = existing
        buffer = []

    for raw in lines:
        canonical, inline = _match_header(raw)
        if canonical:
            flush()
            current = canonical
            if inline:
                buffer.append(inline)
            continue
        buffer.append(raw)

    flush()
    return {k: "\n".join(v).strip() for k, v in sections.items() if "\n".join(v).strip()}


def _enforce_section_order(text: str) -> str:
    """Normalize headers to `## Header` and emit only known sections in canonical order."""
    sections = _split_into_sections(text)
    if not sections:
        return text.strip()

    parts: list[str] = []
    for name in SECTION_ORDER:
        body = sections.get(name)
        if not body:
            continue
        body = re.sub(r"^---+\s*$", "", body, flags=re.MULTILINE).strip()
        if body:
            parts.append(f"## {name}\n\n{body}")
    if not parts:
        return text.strip()
    return "\n\n".join(parts)


def _has_required_sections(text: str) -> bool:
    """An answer is valid if it has a Summary plus at least one other section."""
    sections = _split_into_sections(text)
    if "Summary" not in sections:
        return False
    return len([k for k, v in sections.items() if v]) >= 2


# ---------------------------------------------------------------------------
# Conversation helpers
# ---------------------------------------------------------------------------


def _trim_history(history: list[dict] | None, question: str) -> list[dict]:
    if not history:
        return []
    trimmed: list[dict] = []
    q_norm = question.strip().lower()
    for m in history[-MAX_HISTORY_TURNS * 2:]:
        role = m.get("role")
        content = m.get("content")
        if role not in ("user", "assistant") or not isinstance(content, str):
            continue
        if role == "user" and content.strip().lower() == q_norm:
            continue
        trimmed.append({"role": role, "content": content[:MAX_HISTORY_CHARS]})
    return trimmed[-MAX_HISTORY_TURNS * 2:]


# ---------------------------------------------------------------------------
# Data-grounded local answers — works for ANY question using matched reviews
# ---------------------------------------------------------------------------

_STOPWORDS = frozenset({
    "what", "when", "where", "which", "who", "whom", "whose", "why", "how",
    "does", "do", "did", "are", "is", "was", "were", "the", "and", "for",
    "with", "about", "from", "that", "this", "those", "these", "into", "your",
    "their", "they", "them", "have", "has", "had", "can", "could", "would",
    "should", "will", "been", "being", "most", "more", "some", "such", "than",
    "then", "also", "just", "only", "very", "much", "many", "often", "users",
    "user", "spotify", "music", "tell", "explain", "describe", "list", "show",
})


def _question_tokens(question: str) -> list[str]:
    tokens = [t for t in re.split(r"\W+", question.lower()) if len(t) > 2]
    return [t for t in tokens if t not in _STOPWORDS]


def _theme_relevance(theme: dict[str, Any], question: str) -> int:
    tokens = _question_tokens(question)
    if not tokens:
        return 0
    score = 0
    blob = " ".join(
        str(theme.get(k) or "")
        for k in ("theme_name", "summary", "what_users_want", "dominant_segment")
    ).lower()
    for token in tokens:
        if token in blob:
            score += 3
    return score


def _actions_from_question(
    question: str,
    topic: str,
    pain_keys: list[str],
    intent: str,
) -> list[str]:
    q = question.lower()
    actions: list[str] = list(actions_for_intent(intent, topic))

    if intent == "opportunity":
        return actions[:4] if actions else list(FOCUS_AREA_BY_TOPIC.get(topic, FOCUS_AREA_BY_TOPIC["general"]))[:4]

    if any(w in q for w in ("skip", "dismiss", "ignore", "reject", "hide")):
        actions.append("Strengthen negative feedback signals when users skip or dismiss recommendations.")
    if any(w in q for w in ("leave", "churn", "cancel", "quit", "switch")):
        actions.append("Address retention drivers behind exit feedback before adding new surface area.")
    if any(w in q for w in ("podcast", "audiobook", "spoken")):
        actions.append("Audit podcast and spoken-word discovery flows separately from music recommendations.")
    if any(w in q for w in ("offline", "download")):
        actions.append("Improve offline download reliability, storage management, and playback parity.")
    if any(w in q for w in ("ad", "ads", "free tier", "free plan")):
        actions.append("Test ad pacing changes that protect active discovery sessions on the free tier.")

    topic_actions: dict[str, list[str]] = {
        "discovery": [
            "Launch a dedicated Explore experience for music outside the user's taste profile.",
            "Add discovery-intensity controls so users can request more novelty in playlists.",
        ],
        "repetition": [
            "Introduce loop-detection nudges when repetitive listening patterns are detected.",
            "Redesign autoplay to gradually increase novelty after repeated plays.",
        ],
        "pricing": [
            "Run value-perception research on which Premium features justify subscription cost.",
            "Simplify family and student verification to reduce plan enrollment friction.",
        ],
        "ui": [
            "Reduce tap count on high-frequency flows such as save, share, and queue.",
            "Ship major UI changes gradually with opt-in preview periods.",
        ],
        "performance": [
            "Prioritize crash-free playback as a non-negotiable reliability metric.",
            "Profile and optimize library and search loading on low-end devices.",
        ],
        "social": [
            "Expand collaborative playlists with real-time friend activity signals.",
            "Launch a lightweight social discovery feed for trusted connections.",
        ],
        "catalog": [
            "Show catalog availability clearly in search results and artist pages.",
            "Prioritize closing high-impact regional catalog gaps surfaced in reviews.",
        ],
        "audio": [
            "Make audio quality settings easier to discover and compare across plans.",
            "Improve Bluetooth handoff and wireless playback consistency.",
        ],
        "segment": [
            "Segment onboarding and recommendations by listening style and subscription tier.",
            "Build distinct discovery paths for casual listeners versus power users.",
        ],
    }

    for act in topic_actions.get(topic, topic_actions.get("discovery", [])):
        if act not in actions:
            actions.append(act)

    if not actions:
        actions = list(FOCUS_AREA_BY_TOPIC.get(topic, FOCUS_AREA_BY_TOPIC["general"]))[:3]

    return actions[:4]


def _norm_text(text: str) -> str:
    return re.sub(r"\W+", " ", (text or "").lower()).strip()


def _text_overlap(a: str, b: str) -> float:
    """Rough word overlap ratio between two strings."""
    wa = set(_norm_text(a).split())
    wb = set(_norm_text(b).split())
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / min(len(wa), len(wb))


def _sections_are_distinct(answer: str) -> bool:
    """Reject answers that repeat the same content across sections."""
    sections = _split_into_sections(answer)
    summary = sections.get("Summary") or ""
    pains = sections.get("Key pain points") or ""
    focus = sections.get("Product focus areas") or ""
    actions = sections.get("Recommended actions") or ""

    if _text_overlap(pains, focus) > 0.62:
        return False
    if _text_overlap(focus, actions) > 0.5:
        return False
    if _text_overlap(summary, pains) > 0.72:
        return False
    # Same phrase repeated in focus bullets
    focus_lines = [ln.strip() for ln in focus.splitlines() if ln.strip().startswith("-")]
    seen: set[str] = set()
    for ln in focus_lines:
        core = _norm_text(ln.split(":", 1)[-1] if ":" in ln else ln)
        if core in seen:
            return False
        seen.add(core)
    return True


def _filter_reviews_for_question(
    reviews: list[dict[str, Any]],
    question: str,
    topic: str,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Keep only reviews relevant to the question topic."""
    scored: list[tuple[int, dict[str, Any]]] = []
    for rev in reviews:
        s = score_review_relevance(rev, question, topic)
        if s > 0:
            scored.append((s, rev))
    scored.sort(key=lambda x: x[0], reverse=True)
    filtered = [r for _, r in scored[:limit]]
    if filtered:
        return filtered
    for rev in reviews:
        key = str(rev.get("pain_category") or "").lower()
        if pain_allowed_for_topic(key, topic):
            filtered.append(rev)
        if len(filtered) >= limit:
            break
    return filtered[:limit]


def _collect_review_signals(
    filtered: list[dict[str, Any]],
    question: str,
    topic: str,
) -> list[dict[str, str]]:
    """Extract unique review signals — one per pain category, ranked by relevance."""
    signals: list[dict[str, str]] = []
    seen_cats: set[str] = set()
    seen_needs: set[str] = set()

    for rev in filtered:
        key = str(rev.get("pain_category") or "").lower()
        if not key or key in {"none", "nan"}:
            continue
        if not pain_allowed_for_topic(key, topic):
            continue
        label = format_pain(key)
        if label in seen_cats and topic != "listening_behavior":
            continue

        need = str(rev.get("unmet_need") or "").strip()
        if need.lower() in {"none", "nan", ""}:
            need = ""
        need_norm = _norm_text(need)[:80]
        if need_norm and need_norm in seen_needs:
            continue

        signals.append({"key": key, "label": label, "need": need})
        seen_cats.add(label)
        if need_norm:
            seen_needs.add(need_norm)
        if len(signals) >= 6:
            break
    return signals


def _synthesize_segment_summary(evidence: dict[str, Any]) -> str:
    """Direct answer for segment-comparison questions using structured segment data."""
    segments = evidence.get("user_segments") or []
    if not segments:
        return (
            "Different user segments report distinct discovery challenges shaped by "
            "listening style, playlist dependence, and subscription tier."
        )

    parts: list[str] = []
    for seg in segments[:5]:
        name = (seg.get("name") or "").strip()
        if not name:
            continue
        dc = (seg.get("discovery_challenge") or {}).get("label") or ""
        pf = (seg.get("primary_frustration") or {}).get("label") or ""
        challenge = dc or pf
        if challenge:
            parts.append(f"**{name}** — {challenge.rstrip('.')}")
        elif (seg.get("unmet_need") or {}).get("label"):
            parts.append(f"**{name}** — {(seg['unmet_need']['label']).rstrip('.')}")

    if len(parts) >= 2:
        joined = "; ".join(parts[:4])
        return (
            f"Discovery challenges differ by segment: {joined}. "
            "Each group’s top frustration reflects how they listen and what surfaces they rely on."
        )
    if parts:
        return f"The clearest segment contrast in the data: {parts[0]}."
    return (
        "User segments in the review corpus experience different discovery challenges "
        "based on listening intensity, playlist use, and free vs. premium constraints."
    )


def _synthesize_summary(
    question: str,
    intent: str,
    topic: str,
    signals: list[dict[str, str]],
    evidence: dict[str, Any] | None = None,
) -> str:
    """Build a summary that directly answers the question from review signals."""
    if intent == "segment_question" and evidence:
        return _synthesize_segment_summary(evidence)

    needs: list[str] = []
    for s in signals:
        raw = str(s.get("need") or "").strip()
        if not raw:
            continue
        cleaned = strategic_rewrite(raw).rstrip(".")
        if cleaned in NON_UNMET_NEED_LABELS or cleaned == _GENERIC_NEED:
            continue
        if topic in {"discovery", "recommendations", "repetition"} and cleaned not in DISCOVERY_FOCUSED_NEEDS:
            continue
        if cleaned.lower() not in {n.lower() for n in needs}:
            needs.append(cleaned)
        if len(needs) >= 3:
            break

    if intent == "why_cause" and topic == "discovery":
        return (
            "Users struggle to discover new music because algorithmic feeds keep recycling "
            "familiar artists, exploration beyond playlists like Discover Weekly feels limited, "
            "and listeners lack clear controls to steer toward genuinely unfamiliar music."
        )

    if intent == "opportunity" and topic == "discovery":
        return (
            "The biggest opportunities to improve music discovery are dedicated Explore experiences "
            "outside the taste bubble, user-controlled recommendation novelty, and curator or "
            "social paths that surface unfamiliar artists without relying on past listening alone."
        )

    if intent == "listening_goals" and topic == "listening_behavior":
        if len(needs) >= 2:
            return (
                "Users are trying to achieve varied listening goals — including "
                f"{needs[0].lower()} and {needs[1].lower()} — alongside mood-based sessions, "
                "smarter playlist control, and uninterrupted background listening."
            )
        return summary_for_intent("listening_goals", "listening_behavior")

    if intent == "listening_goals":
        return summary_for_intent("listening_goals", topic)

    if intent == "pain_list" and topic == "pricing":
        return (
            "Free-tier users are most frustrated by aggressive ad frequency during music "
            "and podcasts, interruptions that break listening flow, and the feeling that "
            "ads push them toward Premium without a balanced free experience."
        )

    if intent == "pain_list" and needs:
        joined = ", ".join(n.lower() for n in needs[:3])
        return f"The most cited complaints behind this question are {joined}."

    if intent == "why_cause" and needs:
        return (
            f"The core drivers are {needs[0].lower()}"
            + (f" and {needs[1].lower()}." if len(needs) > 1 else ".")
        )

    if intent == "opportunity":
        return summary_for_intent(intent, topic)

    if needs:
        return (
            f"Review feedback on this question centers on {needs[0].lower()}"
            + (f", {needs[1].lower()}, and related unmet expectations." if len(needs) > 1 else ".")
        )

    return summary_for_intent(intent, topic)


def _build_pain_section(signals: list[dict[str, str]], stats: dict, question: str, topic: str) -> list[str]:
    """Specific user complaints — one bullet per category, from review data only."""
    bullets: list[str] = []
    for sig in signals:
        if len(bullets) >= 4:
            break
        label = sig["label"]
        need = sig.get("need") or ""
        if need:
            bullets.append(f"- **{label}**: {need.rstrip('.')}.")
        elif sig["key"] in PAIN_INSIGHT and not signals:
            bullets.append(f"- **{label}**: {PAIN_INSIGHT[sig['key']]}")

    if len(bullets) < 2 and not signals:
        for key, label, _ in pain_lines(stats, question, limit=4, require_relevant=True):
            if not pain_allowed_for_topic(key, topic):
                continue
            if any(label in b for b in bullets):
                continue
            insight = PAIN_INSIGHT.get(key)
            if insight:
                bullets.append(f"- **{label}**: {insight}")
            if len(bullets) >= 4:
                break
    return bullets[:4]


def _build_focus_section(
    question: str,
    topic: str,
    intent: str,
    themes: list[dict[str, Any]],
    pain_bullets: list[str],
) -> list[str]:
    """Strategic product directions — must NOT repeat pain-point wording."""
    bullets: list[str] = []
    pain_blob = _norm_text("\n".join(pain_bullets))

    area_labels = {
        "discovery": "Exploration",
        "repetition": "Listening diversity",
        "listening_behavior": "Listening modes",
        "pricing": "Monetization",
        "ui": "Experience design",
        "performance": "Reliability",
        "social": "Social discovery",
        "catalog": "Catalog",
        "audio": "Audio quality",
        "segment": "Segmentation",
        "general": "Product",
    }
    area = area_labels.get(topic, "Product")

    if intent == "pain_list" and topic == "pricing":
        ad_focus = (
            "Reduce ad frequency during active music sessions while protecting revenue.",
            "Create a lighter ad policy for podcast and spoken-word listening.",
            "Improve transparency on why ads appear and how Premium removes them.",
        )
        for line in ad_focus:
            if len(bullets) >= 4:
                break
            if _text_overlap(line, pain_blob) < 0.35:
                bullets.append(f"- **Ad experience**: {line}")

    for line in FOCUS_AREA_BY_TOPIC.get(topic, FOCUS_AREA_BY_TOPIC["general"]):
        if len(bullets) >= 4:
            break
        if _text_overlap(line, pain_blob) > 0.45:
            continue
        prefix = "Opportunity" if intent == "opportunity" else area
        bullets.append(f"- **{prefix}**: {line}")

    ranked = sorted(themes, key=lambda t: _theme_relevance(t, question), reverse=True)
    for t in ranked:
        if len(bullets) >= 4:
            break
        name = str(t.get("theme_name") or "").strip()
        if is_noisy_theme(name):
            continue
        summary = str(t.get("summary") or t.get("one_line_summary") or "").strip()
        if summary and _text_overlap(summary, pain_blob) < 0.4:
            bullets.append(f"- **{name}**: {summary.rstrip('.')}.")
        elif t.get("what_users_want"):
            want = str(t["what_users_want"]).strip()
            if _text_overlap(want, pain_blob) < 0.4:
                bullets.append(f"- **{name}**: Invest in {want.lower().rstrip('.')}.")

    return bullets[:4]


def _build_actions_section(
    question: str,
    intent: str,
    topic: str,
    signals: list[dict[str, str]],
    focus_bullets: list[str],
) -> list[str]:
    """Concrete team next steps — distinct from focus areas and pain points."""
    actions: list[str] = []

    intent_actions = {
        "why_cause": {
            "discovery": [
                "Run a journey audit from search to save to find where discovery intent drops off.",
                "Instrument autoplay and Discover Weekly for over-exposure of familiar artists.",
                "Prototype explicit novelty controls and measure lift in new-artist saves.",
            ],
            "pricing": [
                "Analyze ad completion and skip rates during music versus podcast sessions.",
                "Test reduced ad frequency in active listening sessions on the free tier.",
            ],
        },
        "opportunity": {
            "discovery": [
                "Launch a scoped Explore tab MVP targeting content outside the taste profile.",
                "A/B test a discovery-intensity slider on algorithmic playlists.",
                "Pilot curator playlists in one genre as an alternative to pure algorithmic radio.",
            ],
        },
        "pain_list": {
            "pricing": [
                "Benchmark ad load against competitors and set a target cap for music sessions.",
                "Design a lighter ad experience specifically for podcast listening on free tier.",
                "Survey churned free users on whether ad frequency was a primary exit driver.",
            ],
        },
        "listening_goals": {
            "listening_behavior": [
                "Research which listening modes users want (focus, workout, discovery, background) and map current gaps.",
                "Prototype smarter shuffle that avoids short-loop repetition in large playlists.",
                "Test context-aware sessions that keep mood and tempo consistent when autoplay kicks in.",
                "Evaluate separate taste profiles for different listening contexts.",
            ],
        },
    }

    preset = intent_actions.get(intent, {}).get(topic)
    if preset:
        actions.extend(list(preset)[:4])
    else:
        for act in actions_for_intent(intent, topic):
            if act not in actions:
                actions.append(act)
            if len(actions) >= 4:
                break

    return actions[:4]


# ---------------------------------------------------------------------------
# Evidence pack — exact counts/percentages from the dataset for grounding
# ---------------------------------------------------------------------------


def _pct(numerator: int | float, denom: int | float) -> str:
    if not denom:
        return ""
    return f"{round(100 * float(numerator) / float(denom), 1)}%"


def _build_evidence_pack(
    question: str,
    payload: dict[str, Any],
    topic: str,
    intent: str,
) -> dict[str, Any]:
    """Compute real counts/percentages relevant to the question. No fabrication."""
    stats = payload.get("dataset_stats") or {}
    reviews = payload.get("matched_reviews") or []
    total = int(stats.get("total_reviews") or 0)

    pack: dict[str, Any] = {"total_reviews": total}

    if stats.get("discovery_related") is not None and total:
        pack["discovery_related"] = {
            "count": int(stats["discovery_related"]),
            "share": _pct(stats["discovery_related"], total),
        }

    # Pain categories relevant to the question's topic
    pain_counts: dict[str, int] = dict(stats.get("top_pain_categories") or {})
    if pain_counts and total:
        ranked: list[dict[str, Any]] = []
        for key, count in pain_counts.items():
            label = format_pain(str(key))
            relevant = pain_allowed_for_topic(str(key), topic) or topic == "general"
            ranked.append({
                "key": str(key),
                "label": label,
                "count": int(count),
                "share": _pct(count, total),
                "relevant": relevant,
            })
        ranked.sort(key=lambda r: (not r["relevant"], -r["count"]))
        for row in ranked[:8]:
            row["source_counts"] = source_counts_for_pain_category(str(row["key"]))
            enrich_finding(
                row,
                count=row["count"],
                share=row["share"],
                source_counts=row["source_counts"],
            )
        pack["pain_categories"] = ranked[:8]

    # Segment distribution
    seg_counts: dict[str, int] = dict(stats.get("segments") or {})
    if seg_counts and total:
        pack["segments"] = [
            {"label": str(name), "count": int(c), "share": _pct(c, total)}
            for name, c in list(seg_counts.items())[:8]
        ]

    # Source mix
    src_counts: dict[str, int] = dict(stats.get("sources") or {})
    if src_counts and total:
        pack["sources"] = [
            {"label": str(name), "count": int(c), "share": _pct(c, total)}
            for name, c in list(src_counts.items())[:6]
        ]

    # Sentiment mix
    sent_counts: dict[str, int] = dict(stats.get("sentiments") or {})
    if sent_counts and total:
        pack["sentiments"] = [
            {"label": str(name), "count": int(c), "share": _pct(c, total)}
            for name, c in sent_counts.items()
        ]

    # Top unmet needs (already counted by rag.py)
    unmet: dict[str, int] = dict(stats.get("top_unmet_needs") or {})
    if unmet:
        pack["top_unmet_needs"] = [
            {"label": str(name), "count": int(c)}
            for name, c in list(unmet.items())[:6]
        ]

    # Matched review summary for this question
    matched_total = len(reviews)
    if matched_total:
        matched_pains: dict[str, int] = {}
        for rev in reviews:
            key = str(rev.get("pain_category") or "").lower().strip()
            if not key or key in {"none", "nan"}:
                continue
            matched_pains[key] = matched_pains.get(key, 0) + 1
        matched_segments: dict[str, int] = {}
        for rev in reviews:
            seg = str(rev.get("segment") or "").strip()
            if not seg:
                continue
            matched_segments[seg] = matched_segments.get(seg, 0) + 1
        pack["matched_reviews"] = {
            "count": matched_total,
            "share_of_dataset": _pct(matched_total, total) if total else "",
            "top_pain_categories": [
                {
                    "label": format_pain(k),
                    "count": v,
                    "share_of_matched": _pct(v, matched_total),
                }
                for k, v in sorted(matched_pains.items(), key=lambda x: -x[1])[:5]
            ],
            "top_segments": [
                {"label": k, "count": v, "share_of_matched": _pct(v, matched_total)}
                for k, v in sorted(matched_segments.items(), key=lambda x: -x[1])[:5]
            ],
        }

    # Inject dedicated discovery insights when the question is about discovery,
    # repetition, recommendations, or listening behaviour.
    discovery_topics = {"discovery", "recommendations", "listening_behavior", "general"}
    q_lower = question.lower()
    discovery_keywords = (
        "discover", "discovery", "explore", "exploration", "find new", "new music",
        "new artist", "new song", "fresh music",
        "repeat", "repetition", "repetitive", "same song", "same artist", "loop",
        "shuffle", "autoplay", "recommend",
    )
    triggered_by_topic = topic in discovery_topics
    triggered_by_text = any(kw in q_lower for kw in discovery_keywords)
    if triggered_by_topic or triggered_by_text:
        try:
            di = compute_discovery_insights()
            pack["discovery_insights"] = _select_discovery_sections(di, question)
        except Exception:  # pragma: no cover - never block answer on this
            logger.exception("Failed to attach discovery insights to evidence pack")

    # Inject root-cause analysis on cause/why/driver questions.
    if intent == "why_cause" or any(k in q_lower for k in (
        "why", "cause", "reason", "driver", "behind", "root cause",
    )):
        try:
            rc = compute_root_causes()
            top = [c for c in rc.get("causes", []) if c.get("count")][:6]
            if top:
                pack["root_causes"] = [
                    enrich_finding(
                        {
                            "label": c["label"],
                            "summary": c["summary"],
                            "count": c["count"],
                            "share_of_corpus": c["share_of_corpus"],
                            "top_pain_categories": c["top_pain_categories"],
                            "source_counts": c.get("source_counts") or {},
                        },
                        count=c["count"],
                        share=c["share_of_corpus"],
                        source_counts=c.get("source_counts") or {},
                    )
                    for c in top
                ]
        except Exception:  # pragma: no cover
            logger.exception("Failed to attach root causes to evidence pack")

    # Inject segment insights when the question is about specific user types.
    segment_keywords = (
        "segment", "user type", "user group",
        "premium", "free user", "free tier", "paid",
        "heavy", "casual", "discovery seeker", "playlist user",
        "who is", "which users", "which group",
    )
    if intent == "segment_question" or any(k in q_lower for k in segment_keywords):
        try:
            us = compute_user_segments()
            relevant = _select_relevant_segments(us, q_lower)
            if relevant:
                pack["user_segments"] = relevant
        except Exception:  # pragma: no cover
            logger.exception("Failed to attach user segments to evidence pack")

    pack["intent"] = intent
    pack["topic"] = topic

    # Pre-rank the strongest, statistically-meaningful findings so both Groq
    # and the deterministic builder can render confidence-building Evidence.
    pack["findings"] = _collect_evidence_findings(pack)
    return pack


def _select_relevant_segments(us: dict[str, Any], q_lower: str) -> list[dict[str, Any]]:
    """Pick segments mentioned by the question; default to top 3 by size."""
    segments = us.get("segments") or []
    if not segments:
        return []
    name_keywords: dict[str, tuple[str, ...]] = {
        "Discovery Seeker": ("discovery seeker", "seeker"),
        "Playlist User": ("playlist user", "playlist users", "playlist-driven"),
        "Heavy Listener": ("heavy listener", "heavy user", "power user"),
        "Casual Listener": ("casual listener", "casual user", "occasional"),
        "Premium User": ("premium", "paid", "subscriber"),
        "Free User": ("free user", "free tier", "free-tier", "ad-supported", "ad tier"),
    }
    picked: list[dict[str, Any]] = []
    for seg in segments:
        if any(kw in q_lower for kw in name_keywords.get(seg["name"], ())):
            picked.append(seg)
    if not picked:
        if any(k in q_lower for k in (
            "different", "each segment", "all segment", "compare segment",
            "which user segment", "user segments", "different discovery",
        )):
            picked = sorted(segments, key=lambda s: -(s.get("count") or 0))
        else:
            picked = sorted(segments, key=lambda s: -(s.get("count") or 0))[:3]
    return [
        {
            "name": s["name"],
            "description": s["description"],
            "count": s["count"],
            "share_of_corpus": s["share_of_corpus"],
            "primary_frustration": s.get("primary_frustration"),
            "discovery_challenge": s.get("discovery_challenge"),
            "unmet_need": s.get("unmet_need"),
        }
        for s in picked
    ]


def _select_discovery_sections(di: dict[str, Any], question: str) -> dict[str, Any]:
    """Return only the discovery insight sections relevant to the question."""
    q = question.lower()
    sections: list[str] = []
    if any(k in q for k in ("repeat", "repetition", "repetitive", "same song", "same artist", "loop", "shuffle", "autoplay")):
        sections.append("repetition_causes")
    if any(k in q for k in ("frustrat", "annoy", "complain", "complaint", "hate", "dislike", "problem", "issue", "pain")):
        sections.append("discovery_frustrations")
        sections.append("discovery_struggles")
    if any(k in q for k in ("need", "want", "wish", "should", "opportunity", "improve", "fix")):
        sections.append("discovery_unmet_needs")
    if any(k in q for k in ("why", "cause", "struggle", "hard", "difficult", "can't", "cannot", "discover", "discovery", "find new", "exploration", "explore")):
        sections.append("discovery_struggles")
    # Default: when no specific keyword matches, return all 4 so the LLM can pick.
    if not sections:
        sections = ["discovery_struggles", "repetition_causes", "discovery_frustrations", "discovery_unmet_needs"]
    sections = list(dict.fromkeys(sections))
    out: dict[str, Any] = {"totals": di.get("totals", {})}
    for key in sections:
        block = di.get(key) or {}
        groups = [g for g in (block.get("groups") or []) if not g["label"].startswith("Other")][:5]
        if not groups and block.get("groups"):
            groups = block["groups"][:3]
        if not groups:
            continue
        out[key] = {
            "description": block.get("description"),
            "pool_size": block.get("pool_size"),
            "pool_share_of_corpus": block.get("pool_share_of_corpus"),
            "groups": groups,
        }
    return out


# ---------------------------------------------------------------------------
# 8-section data-grounded answer (used when Groq is unavailable)
# ---------------------------------------------------------------------------


# Prose phrases for known group labels — used to make Evidence bullets read
# naturally rather than echoing raw category labels. Anything missing falls
# back to a generic "mention <Label>" phrasing.
_FINDING_PROSE: dict[str, str] = {
    # Discovery struggles
    "Hard to find new artists or genres": "mention difficulty finding new artists or genres",
    "Discover Weekly / Release Radar feel stale": "report stale Discover Weekly or Release Radar feeds",
    "Recommendations feel irrelevant or off-target": "describe recommendations as irrelevant or off-target",
    "Algorithm reinforces what users already listen to": "say the algorithm keeps surfacing what they already listen to",
    "Limited paths to explore outside taste profile": "want more ways to explore outside their taste profile",
    "Algorithm doesn't learn from feedback": "say the algorithm doesn't learn from their feedback",
    "Mainstream bias hurts niche-genre listeners": "feel niche genres are underserved versus mainstream",
    "Ads break the discovery flow on free tier": "say ads break their discovery flow on the free tier",
    # Repetition causes
    "Shuffle replays a small pool of tracks": "say shuffle replays the same small pool of tracks",
    "Autoplay/Radio cycles the same artists": "say autoplay or radio cycles the same artists",
    "Recommendation engine keeps surfacing favorites": "say recommendations keep surfacing familiar favourites",
    "Discover Weekly recycles known tracks": "say Discover Weekly recycles tracks they already know",
    "Single play permanently skews future suggestions": "say a single play permanently skews future suggestions",
    "Library / queue keeps looping back": "describe their library or queue looping back",
    "Algorithm interprets repeat plays as strong preference": "say repeat plays get over-weighted by the algorithm",
    # Frustrations
    "Recommendations feel stale and repetitive": "describe recommendations as stale or repetitive",
    "Hard to escape past listening history": "say it's hard to escape past listening history",
    "Algorithm doesn't understand my taste": "say the algorithm doesn't understand their taste",
    "Discover Weekly disappoints over time": "say Discover Weekly has degraded over time",
    "Ads disrupt active music exploration": "say ads disrupt active music exploration",
    "Skipping songs doesn't seem to teach the algorithm": "say skipping songs doesn't teach the algorithm",
    "Wanted curator/social/human picks but only get algorithmic ones": "want curator or human picks instead of pure algorithmic ones",
    # Unmet needs
    "More diverse recommendations": "want more diverse recommendations",
    "Better personalization that learns from feedback": "want personalization that actually learns from feedback",
    "Dedicated discovery surfaces beyond Discover Weekly": "want a dedicated discovery surface beyond Discover Weekly",
    "User control over algorithmic intensity / novelty": "want more control over algorithmic novelty",
    "Smarter shuffle and autoplay": "want smarter shuffle and autoplay behaviour",
    "Curator- or human-driven discovery": "want curator- or human-driven discovery",
    "Social and friend-based discovery": "want social or friend-based discovery",
    "Mood and context-aware recommendations": "want mood and context-aware recommendations",
    "Fresher and more accurate recommendations": "want fresher and more accurate recommendations",
    "Easier music discovery (general)": "want music discovery to feel simpler overall",
    # Root causes
    "Over-personalization": "cite over-personalization in recommendations",
    "Genre repetition": "cite genre repetition",
    "Playlist dependency": "say discovery depends too heavily on Discover Weekly and curated playlists",
    "Weak exploration tools": "cite weak exploration tools as a root cause",
    "Feedback signals don't tune the algorithm": "say their feedback (skips, dislikes) doesn't tune the algorithm",
    "Mainstream bias": "say the algorithm has a mainstream bias",
    "Ad disruption (free tier)": "cite ad disruption on the free tier",
    "Pricing & value friction": "cite pricing or value friction",
    "Catalog gaps": "report catalog or availability gaps",
    "Performance & stability": "report performance or stability issues",
    "UI / navigation friction": "cite UI or navigation friction",
}

# Minimum count we'll show as evidence. Anything smaller looks statistically
# weak — drop it to keep the Evidence section confidence-building.
_MIN_EVIDENCE_COUNT = 10

_POOL_LABELS: dict[str, str] = {
    "discovery_struggles": "of discovery-related",
    "repetition_causes": "of repetition-related",
    "discovery_frustrations": "of negative discovery feedback",
    "discovery_unmet_needs": "of discovery-related",
    "root_causes": "of total",
    "user_segments": "of total",
    "pain_categories": "of total",
}


def _prose_for_label(label: str) -> str:
    return _FINDING_PROSE.get(label) or f"mention **{label}**"


_GENERIC_PAIN_KEYS = {"none", "nan", "", "other"}
_GENERIC_PAIN_LABELS = {"general feedback", "none", "other"}


def _collect_evidence_findings(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    """Collect ranked findings with meaningful sample sizes.

    Returns specific patterns first (discovery groups, root causes,
    segment-scoped findings) and then broad pain-category counts as fillers.
    Each finding is a dict: ``{count, share, pool, label, prose, source, priority}``.
    Skips anything below ``_MIN_EVIDENCE_COUNT`` and dedupes by prose so the
    same pattern doesn't repeat.
    """
    primary: list[dict[str, Any]] = []
    secondary: list[dict[str, Any]] = []

    di = evidence.get("discovery_insights") or {}
    for section_key in (
        "discovery_struggles",
        "repetition_causes",
        "discovery_frustrations",
        "discovery_unmet_needs",
    ):
        block = di.get(section_key) or {}
        for group in block.get("groups") or []:
            label = group.get("label") or ""
            if not label or label.startswith("Other"):
                continue
            count = int(group.get("count") or 0)
            if count < _MIN_EVIDENCE_COUNT:
                continue
            primary.append(enrich_finding({
                "count": count,
                "share": group.get("share_of_pool") or group.get("share_of_corpus") or "",
                "pool": _POOL_LABELS[section_key],
                "label": label,
                "prose": _prose_for_label(label),
                "source": section_key,
                "source_counts": group.get("source_counts") or {},
            }))

    for rc in evidence.get("root_causes") or []:
        count = int(rc.get("count") or 0)
        if count < _MIN_EVIDENCE_COUNT:
            continue
        primary.append(enrich_finding({
            "count": count,
            "share": rc.get("share_of_corpus") or "",
            "pool": _POOL_LABELS["root_causes"],
            "label": rc.get("label") or "",
            "prose": _prose_for_label(rc.get("label") or ""),
            "source": "root_causes",
            "source_counts": rc.get("source_counts") or {},
        }))

    # Segment-scoped findings: "X reviews (Y% of Premium User segment) cite Z".
    for seg in evidence.get("user_segments") or []:
        seg_count = int(seg.get("count") or 0)
        if seg_count < _MIN_EVIDENCE_COUNT:
            continue
        seg_name = seg.get("name") or ""
        pool = f"of {seg_name} segment"
        pf = seg.get("primary_frustration") or {}
        if pf.get("count") and int(pf["count"]) >= _MIN_EVIDENCE_COUNT:
            primary.append(enrich_finding({
                "count": int(pf["count"]),
                "share": pf.get("share_of_segment") or "",
                "pool": pool,
                "label": f"{seg_name} primary frustration",
                "prose": f"describe **{pf.get('label')}** as their top frustration",
                "source": "user_segments",
                "source_counts": seg.get("source_counts") or {},
            }))
        un = seg.get("unmet_need") or {}
        if un.get("count") and int(un["count"]) >= _MIN_EVIDENCE_COUNT:
            un_label = (un.get("label") or "").rstrip(".")
            primary.append(enrich_finding({
                "count": int(un["count"]),
                "share": un.get("share_of_segment") or "",
                "pool": pool,
                "label": f"{seg_name} unmet need",
                "prose": f"express the unmet need: **{un_label}**",
                "source": "user_segments",
                "source_counts": seg.get("source_counts") or {},
            }))

    for item in evidence.get("pain_categories") or []:
        count = int(item.get("count") or 0)
        if count < _MIN_EVIDENCE_COUNT:
            continue
        key = str(item.get("key") or "").lower().strip()
        label = item.get("label") or ""
        if key in _GENERIC_PAIN_KEYS or label.lower() in _GENERIC_PAIN_LABELS:
            continue
        secondary.append(enrich_finding({
            "count": count,
            "share": item.get("share") or "",
            "pool": _POOL_LABELS["pain_categories"],
            "label": label,
            "prose": f"fall under **{label}**",
            "source": "pain_categories",
            "source_counts": item.get("source_counts") or {},
        }))

    primary.sort(key=lambda f: -(f["count"] or 0))
    secondary.sort(key=lambda f: -(f["count"] or 0))
    ranked = primary + secondary

    if evidence.get("intent") == "segment_question":
        segment_first = [f for f in ranked if f.get("source") == "user_segments"]
        other = [f for f in ranked if f.get("source") != "user_segments"]
        ranked = segment_first + other

    return ranked


def _evidence_section_lines(evidence: dict[str, Any]) -> list[str]:
    """Render the Evidence section using full-dataset numbers only.

    Format:
        **Total Reviews Analyzed:** 1,876
        **Discovery-Related Reviews:** 619 (33.0%)

        - {count} reviews ({pct} of {pool}) {prose}.
    """
    lines: list[str] = []
    total = evidence.get("total_reviews") or 0
    if total:
        lines.append(f"**Total Reviews Analyzed:** {total:,}")
    discovery = evidence.get("discovery_related")
    if isinstance(discovery, dict) and discovery.get("count"):
        share = discovery.get("share") or ""
        share_suffix = f" ({share})" if share else ""
        lines.append(f"**Discovery-Related Reviews:** {discovery['count']:,}{share_suffix}")
    if lines:
        lines.append("")  # blank line before findings

    findings = _collect_evidence_findings(evidence)
    seen_prose: set[str] = set()
    findings_added = 0
    for f in findings:
        if f["prose"] in seen_prose:
            continue
        seen_prose.add(f["prose"])
        share = f.get("share") or ""
        pool = f.get("pool") or "of total"
        share_part = f"{share} {pool}".strip()
        label = f.get("label") or ""
        title = f"**{label}** — " if label else ""
        if share_part:
            lines.append(f"- {title}{f['count']:,} reviews ({share_part}) {f['prose']}.")
        else:
            lines.append(f"- {title}{f['count']:,} reviews {f['prose']}.")
        if f.get("confidence") and f.get("confidence_support"):
            lines.extend(confidence_markdown_lines(f["confidence"], f["confidence_support"]))
        findings_added += 1
        if findings_added >= 8:
            break

    # If we couldn't surface any meaningful findings, drop the header lines
    # too — better to omit Evidence than show only totals.
    if findings_added == 0:
        return []
    return lines


_LABEL_TO_PAIN_KEY: dict[str, str] = {
    "Algorithm & Recommendations": "recommendation_quality",
    "UI/UX Issues": "ui_ux",
    "Pricing & Value": "pricing",
    "Catalog & Availability": "content_availability",
    "Listening Behavior": "listening_behavior",
    "Social Features": "social_features",
    "Music Discovery": "discovery",
    "Performance & Stability": "performance",
    "Ads & Free Tier": "ads",
    "Audio Quality": "audio_quality",
    "General Feedback": "none",
}


def _mentions(count: int | float | None) -> str:
    try:
        n = int(count or 0)
    except (TypeError, ValueError):
        return ""
    if n == 0:
        return ""
    return f"{n} mention" if n == 1 else f"{n} mentions"


def _pain_section_lines(evidence: dict[str, Any], topic: str) -> list[str]:
    """Key pain points — one bullet per category with the right insight per category."""
    lines: list[str] = []
    matched = evidence.get("matched_reviews") or {}
    pool = matched.get("top_pain_categories") or evidence.get("pain_categories") or []
    conf_by_key = {
        str(item.get("key") or "").lower(): item
        for item in (evidence.get("pain_categories") or [])
        if item.get("key")
    }
    seen: set[str] = set()
    for item in pool:
        label = item.get("label") or ""
        if not label or label in seen:
            continue
        key = (item.get("key") or _LABEL_TO_PAIN_KEY.get(label) or "").lower()
        if key and topic and topic != "general" and not pain_allowed_for_topic(key, topic):
            continue
        insight = PAIN_INSIGHT.get(key) or summary_for_intent("pain_list", topic)
        count = item.get("count")
        share = item.get("share_of_matched") or item.get("share") or ""
        mentions = _mentions(count)
        suffix_bits = [b for b in (mentions, share) if b]
        suffix = f" ({', '.join(suffix_bits)})" if suffix_bits else ""
        lines.append(f"- **{label}**{suffix}: {insight}")
        conf_item = conf_by_key.get(key) or item
        conf_level = conf_item.get("confidence")
        conf_support = conf_item.get("confidence_support")
        if not conf_level or not conf_support:
            enriched = enrich_finding(
                {
                    "count": count,
                    "share": share,
                    "source_counts": conf_item.get("source_counts")
                    or source_counts_for_pain_category(key),
                },
                count=count,
                share=share,
            )
            conf_level = enriched.get("confidence")
            conf_support = enriched.get("confidence_support")
        if conf_level and conf_support:
            lines.extend(confidence_markdown_lines(conf_level, conf_support))
        seen.add(label)
        if len(lines) >= 5:
            break
    return lines


def _root_cause_lines(
    payload: dict[str, Any],
    evidence: dict[str, Any],
    question: str,
    topic: str,
) -> list[str]:
    """Root causes — paraphrase unmet-need patterns from matched reviews + themes."""
    causes: list[str] = []
    seen: set[str] = set()

    # Seed from structured root-cause analysis when attached.
    for rc in (evidence.get("root_causes") or [])[:3]:
        label = (rc.get("label") or "").strip()
        if not label:
            continue
        norm = _norm_text(label)[:100]
        if norm in seen:
            continue
        count = rc.get("count")
        share = rc.get("share_of_corpus") or ""
        suffix_bits = [b for b in (_mentions(count), share and f"{share} of corpus") if b]
        suffix = f" ({', '.join(suffix_bits)})" if suffix_bits else ""
        summary = (rc.get("summary") or "").rstrip(".")
        causes.append(f"- **{label}**{suffix}: {summary}.")
        if rc.get("confidence") and rc.get("confidence_support"):
            causes.extend(confidence_markdown_lines(rc["confidence"], rc["confidence_support"]))
        seen.add(norm)
        if len(causes) >= 4:
            break

    # Then seed from grouped discovery insights when relevant.
    discovery = evidence.get("discovery_insights") or {}
    seed_keys: list[tuple[str, str]] = []
    q_lower = question.lower()
    if any(k in q_lower for k in ("repeat", "repetition", "repetitive", "same", "loop", "shuffle", "autoplay")):
        seed_keys.append(("repetition_causes", "Repetition driver"))
    if any(k in q_lower for k in ("why", "cause", "struggle", "hard", "difficult", "discover", "find")):
        seed_keys.append(("discovery_struggles", "Discovery struggle"))
    for section_key, label_prefix in seed_keys:
        if len(causes) >= 4:
            break
        block = discovery.get(section_key) or {}
        for group in (block.get("groups") or [])[:3]:
            label = group.get("label") or ""
            if not label:
                continue
            norm = _norm_text(label)[:100]
            if norm in seen:
                continue
            count = group.get("count")
            share = group.get("share_of_pool") or group.get("share_of_corpus") or ""
            suffix_bits = [b for b in (_mentions(count), share) if b]
            suffix = f" ({', '.join(suffix_bits)})" if suffix_bits else ""
            line = f"- **{label_prefix}**: {label.rstrip('.')}.{suffix}"
            causes.append(line)
            conf_level = group.get("confidence")
            conf_support = group.get("confidence_support")
            if not conf_level or not conf_support:
                enriched = enrich_finding(
                    {"count": count, "share": share, "source_counts": group.get("source_counts") or {}},
                    count=count,
                    share=share,
                    source_counts=group.get("source_counts") or {},
                )
                conf_level = enriched.get("confidence")
                conf_support = enriched.get("confidence_support")
            if conf_level and conf_support:
                causes.extend(confidence_markdown_lines(conf_level, conf_support))
            seen.add(norm)
            if len(causes) >= 4:
                break

    reviews = payload.get("matched_reviews") or []
    filtered = _filter_reviews_for_question(reviews, question, topic, limit=12)
    for rev in filtered:
        need = str(rev.get("unmet_need") or "").strip()
        if not need or need.lower() in {"none", "nan"}:
            continue
        norm = _norm_text(need)[:100]
        if norm in seen:
            continue
        pain_key = str(rev.get("pain_category") or "").lower()
        if pain_key and not pain_allowed_for_topic(pain_key, topic) and topic != "general":
            continue
        label = format_pain(pain_key) if pain_key else "Underlying driver"
        causes.append(f"- **{label}**: {need.rstrip('.')}.")
        seen.add(norm)
        if len(causes) >= 4:
            break

    if len(causes) < 3:
        for theme in (payload.get("themes") or [])[:6]:
            name = str(theme.get("theme_name") or "").strip()
            if not name or is_noisy_theme(name):
                continue
            want = str(theme.get("what_users_want") or theme.get("summary") or "").strip()
            if not want:
                continue
            norm = _norm_text(want)[:100]
            if norm in seen:
                continue
            causes.append(f"- **{name}**: {want.rstrip('.')}.")
            seen.add(norm)
            if len(causes) >= 4:
                break
    return causes


def _segment_lines(evidence: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()

    # Prefer the structured 6-segment classification when attached.
    for seg in (evidence.get("user_segments") or [])[:6]:
        name = (seg.get("name") or "").strip()
        if not name or name in seen:
            continue
        count = seg.get("count")
        share = seg.get("share_of_corpus") or ""
        noun = "1 review" if count == 1 else f"{count:,} reviews" if count else ""
        suffix_bits = [b for b in (noun, share) if b]
        suffix = f" ({', '.join(suffix_bits)})" if suffix_bits else ""
        bits: list[str] = []
        pf = seg.get("primary_frustration") or {}
        if pf.get("label"):
            bits.append(f"primary frustration: {pf['label']}")
        dc = seg.get("discovery_challenge") or {}
        if dc.get("label"):
            bits.append(f"discovery challenge: {dc['label']}")
        un = seg.get("unmet_need") or {}
        if un.get("label"):
            bits.append(f"unmet need: {un['label']}")
        detail = " — " + "; ".join(bits) if bits else ""
        lines.append(f"- **{name}**{suffix}{detail}.")
        seen.add(name)

    if lines:
        return lines

    matched = (evidence.get("matched_reviews") or {}).get("top_segments") or []
    pool = matched or evidence.get("segments") or []
    for item in pool[:5]:
        label = item.get("label") or ""
        count = item.get("count")
        share = item.get("share_of_matched") or item.get("share") or ""
        if not label:
            continue
        pretty = format_segment(label) if label and not label.startswith("**") else label
        mentions = ("1 review" if count == 1 else f"{count} reviews") if count else ""
        suffix_bits = [b for b in (mentions, share) if b]
        suffix = f" ({', '.join(suffix_bits)})" if suffix_bits else ""
        lines.append(f"- **{pretty}**{suffix}")
    return lines


_GENERIC_NEED = "Need a more reliable music experience"


def _unmet_need_lines(payload: dict[str, Any], evidence: dict[str, Any], question: str, topic: str) -> list[str]:
    """Strategic unmet needs — discovery-focused first, deduped canonically.

    Pulls candidates from (a) the grouped discovery_unmet_needs evidence,
    (b) matched-review unmet_need values, and (c) the top_unmet_needs roll-up.
    Each candidate is canonicalised with ``strategic_rewrite`` so semantic
    siblings collapse to one bullet, and discovery-related needs are sorted
    first when the question touches discovery / repetition / recommendations.
    """
    q_lower = question.lower()
    discovery_question = topic in {"discovery", "recommendations", "listening_behavior"} or any(
        k in q_lower for k in (
            "discover", "discovery", "explore", "exploration", "new music",
            "new artist", "fresh", "diverse", "recommend", "personali",
            "shuffle", "autoplay", "repeat", "repetition",
        )
    )

    candidates: dict[str, dict[str, Any]] = {}

    def _add(label_in: str, count: int | None = None, share: str | None = None) -> None:
        label = strategic_rewrite(label_in)
        if not label or label == _GENERIC_NEED or label in NON_UNMET_NEED_LABELS:
            return
        bucket = candidates.setdefault(label, {"count": 0, "share": "", "label": label, "locked": False})
        if share and not bucket["share"]:
            bucket["share"] = share
            bucket["count"] = int(count or 0)
            bucket["locked"] = True
            return
        if not bucket["locked"] and count:
            bucket["count"] += int(count)

    discovery_block = (evidence.get("discovery_insights") or {}).get("discovery_unmet_needs") or {}
    for group in discovery_block.get("groups") or []:
        label = str(group.get("label") or "").strip()
        if not label or label.startswith("Other"):
            continue
        _add(
            label,
            count=group.get("count"),
            share=group.get("share_of_pool") or group.get("share_of_corpus"),
        )

    reviews = payload.get("matched_reviews") or []
    for rev in _filter_reviews_for_question(reviews, question, topic, limit=30):
        need = str(rev.get("unmet_need") or "").strip()
        if not need or need.lower() in {"none", "nan"}:
            continue
        _add(need, count=1)

    for item in evidence.get("top_unmet_needs") or []:
        label = str(item.get("label") or "").strip()
        if not label:
            continue
        _add(label, count=item.get("count"))

    if not candidates:
        return []

    def _sort_key(b: dict[str, Any]) -> tuple[int, int]:
        discovery_priority = 0 if (discovery_question and b["label"] in DISCOVERY_FOCUSED_NEEDS) else 1
        return (discovery_priority, -(b["count"] or 0))

    ranked = sorted(candidates.values(), key=_sort_key)

    lines: list[str] = []
    for b in ranked[:5]:
        share = b.get("share") or ""
        suffix_bits = [bit for bit in (_mentions(b["count"]), share) if bit]
        suffix = f" ({', '.join(suffix_bits)})" if suffix_bits else ""
        lines.append(f"- {b['label'].rstrip('.')}.{suffix}")
    return lines


def _focus_area_lines(question: str, topic: str, intent: str, payload: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()
    for area in FOCUS_AREA_BY_TOPIC.get(topic, FOCUS_AREA_BY_TOPIC["general"]):
        norm = _norm_text(area)[:120]
        if norm in seen:
            continue
        prefix = "Opportunity" if intent == "opportunity" else "Direction"
        lines.append(f"- **{prefix}**: {area}")
        seen.add(norm)
        if len(lines) >= 4:
            break

    for theme in (payload.get("themes") or [])[:6]:
        name = str(theme.get("theme_name") or "").strip()
        if not name or is_noisy_theme(name):
            continue
        want = str(theme.get("what_users_want") or theme.get("summary") or "").strip()
        if not want:
            continue
        norm = _norm_text(want)[:120]
        if norm in seen:
            continue
        lines.append(f"- **{name}**: {want.rstrip('.')}.")
        seen.add(norm)
        if len(lines) >= 5:
            break
    return lines


def _action_lines(question: str, intent: str, topic: str) -> list[str]:
    actions = list(actions_for_intent(intent, topic))
    if not actions:
        actions = [
            "Run a journey audit on the flows tied to this question and identify top friction points.",
            "Design a measurable two-week product experiment targeting the most common review complaint.",
            "Add lightweight in-product feedback prompts to validate the hypothesis behind this question.",
        ]
    return [f"- {a.rstrip('.') }." for a in actions[:5]]


def _build_data_grounded_answer(question: str, payload: dict[str, Any]) -> str:
    """Build an 8-section answer tailored to the question. Sections are omitted when unsupported."""
    topic = detect_topic(question)
    intent = detect_question_intent(question)
    evidence = _build_evidence_pack(question, payload, topic, intent)

    summary = _synthesize_summary(
        question, intent, topic,
        _collect_review_signals(
            _filter_reviews_for_question(payload.get("matched_reviews") or [], question, topic),
            question, topic,
        ),
        evidence=evidence,
    )

    candidates: list[tuple[str, str]] = []
    candidates.append(("Summary", summary))

    ev_lines = _evidence_section_lines(evidence)
    if ev_lines:
        candidates.append(("Evidence", "\n".join(ev_lines)))

    pain_lines_out = _pain_section_lines(evidence, topic)
    if pain_lines_out:
        candidates.append(("Key Pain Points", "\n".join(pain_lines_out)))

    cause_lines = _root_cause_lines(payload, evidence, question, topic)
    if cause_lines:
        candidates.append(("Root Causes", "\n".join(cause_lines)))

    seg_lines = _segment_lines(evidence)
    if seg_lines:
        candidates.append(("Affected User Segments", "\n".join(seg_lines)))

    need_lines = _unmet_need_lines(payload, evidence, question, topic)
    if need_lines:
        candidates.append(("Unmet Needs", "\n".join(need_lines)))

    focus_lines = _focus_area_lines(question, topic, intent, payload)
    if focus_lines:
        candidates.append(("Product Focus Areas", "\n".join(focus_lines)))

    action_lines = _action_lines(question, intent, topic)
    if action_lines:
        candidates.append(("Recommended Actions", "\n".join(action_lines)))

    # Intent-aware section filter — keep only what serves the user's question.
    preferred = set(INTENT_SECTIONS.get(intent, INTENT_SECTIONS["general"]))
    preferred.update(REQUIRED_SECTIONS)
    selected = [(name, body) for name, body in candidates if name in preferred]
    if len(selected) < 3:
        selected = candidates  # fall back to everything we have

    parts = [f"## {name}\n\n{body}" for name, body in selected if body]
    return _strip_ids_and_quotes("\n\n".join(parts))


def _is_canned_fallback_answer(text: str) -> bool:
    """Detect static template or meta-descriptive answers that ignore the question."""
    markers = (
        "Analysis of Spotify user feedback reveals that the most significant areas of concern",
        "Indexed review feedback surfaces recurring themes",
        "indexed reviews tie this question to",
        "Reviews cluster around",
        "Regarding **",
        "Users report ongoing friction related to technical",
        "Prioritize the pain areas most tied to the question asked",
        "Users struggle to discover new music primarily because the algorithm heavily favors",
    )
    lower = text.lower()
    return any(m.lower() in lower for m in markers)


def _ensure_required_sections(answer: str, question: str, payload: dict[str, Any]) -> str:
    """Backfill any missing required section from the data-grounded fallback."""
    sections = _split_into_sections(answer)
    if all(name in sections for name in REQUIRED_SECTIONS) and len(sections) >= 2:
        return _enforce_section_order(answer)
    fallback = _split_into_sections(_build_data_grounded_answer(question, payload))
    for name in SECTION_ORDER:
        if name not in sections and fallback.get(name):
            sections[name] = fallback[name]
    parts = [f"## {name}\n\n{sections[name].strip()}" for name in SECTION_ORDER if sections.get(name)]
    return "\n\n".join(parts) if parts else _build_data_grounded_answer(question, payload)


def _compact_grounding_payload(
    payload: dict[str, Any],
    evidence: dict[str, Any] | None = None,
    limit: int = 10,
) -> str:
    """Smaller context for a fast Groq retry when the full payload times out."""
    slim = {
        "evidence": evidence or {},
        "matched_reviews": [
            {
                "source": r.get("source"),
                "pain_category": r.get("pain_category"),
                "segment": r.get("segment"),
                "unmet_need": r.get("unmet_need"),
                "sentiment": r.get("sentiment"),
            }
            for r in (payload.get("matched_reviews") or [])[:limit]
        ],
        "themes": [
            {
                "theme_name": t.get("theme_name"),
                "summary": t.get("one_line_summary") or t.get("summary"),
                "what_users_want": t.get("what_users_want"),
            }
            for t in (payload.get("themes") or [])[:5]
            if not is_noisy_theme(str(t.get("theme_name") or ""))
        ],
    }
    return json.dumps(slim, ensure_ascii=False, default=str)


_INTENT_GUIDANCE: dict[str, str] = {
    "why_cause": (
        "Question type: WHY/CAUSE — explain the root causes behind the pain. "
        "Lead with Summary, then Evidence, then Key Pain Points, Root Causes, "
        "and Recommended Actions. Skip sections that the data does not back."
    ),
    "opportunity": (
        "Question type: OPPORTUNITY — surface product directions to invest in. "
        "Lead with Summary, then Evidence, then Unmet Needs, Product Focus Areas, "
        "and Recommended Actions. Skip Pain Points unless directly relevant."
    ),
    "pain_list": (
        "Question type: PAIN LIST — describe the concrete complaints. "
        "Lead with Summary, then Evidence, then Key Pain Points and Affected "
        "User Segments, then Recommended Actions."
    ),
    "listening_goals": (
        "Question type: LISTENING GOALS — describe what users are trying to do. "
        "Lead with Summary, Evidence, Unmet Needs, Affected User Segments, and "
        "Product Focus Areas."
    ),
    "segment_question": (
        "Question type: SEGMENT — describe who is impacted. Lead with Summary, "
        "Evidence, Affected User Segments, then Key Pain Points and Recommended Actions."
    ),
    "general": (
        "Question type: GENERAL — answer directly and include only the sections "
        "supported by the supplied review data."
    ),
}


def _build_groq_messages(
    question: str,
    payload: dict[str, Any],
    grounding: str,
    history: list[dict],
    *,
    evidence: dict[str, Any] | None = None,
    compact: bool = False,
) -> list[dict]:
    intent = detect_question_intent(question)
    topic = detect_topic(question)
    guidance = _INTENT_GUIDANCE.get(intent, _INTENT_GUIDANCE["general"])

    if evidence is None:
        evidence = _build_evidence_pack(question, payload, topic, intent)

    # Keep the small "matched_reviews" subset out of the LLM context — its
    # tiny denominator makes Evidence look statistically weak.
    evidence_for_prompt = {k: v for k, v in evidence.items() if k != "matched_reviews"}
    evidence_block = json.dumps(evidence_for_prompt, ensure_ascii=False, default=str)
    prefix = (
        "COMPACT CONTEXT — same rules: include only sections the data supports.\n\n"
        if compact else ""
    )

    user_content = (
        f"QUESTION (answer this exactly — never give a generic overview):\n{question}\n\n"
        f"{guidance}\n\n"
        "Detected topic for filtering pain categories: "
        f"`{topic}` (use this hint, do not mention it).\n\n"
        "EVIDENCE (use ONLY these numbers — never invent percentages):\n"
        f"{evidence_block}\n\n"
        f"{prefix}REVIEW CONTEXT:\n{grounding}\n\n"
        "Reminder: output the markdown sections only, omit sections without "
        "supporting data, and never repeat the same point across sections."
    )

    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_content})
    return messages


def _accept_groq_answer(raw: str, question: str, payload: dict[str, Any]) -> str | None:
    """Accept Groq output when it has a Summary plus at least one supporting section."""
    cleaned = _strip_ids_and_quotes(raw)
    normalized = _enforce_section_order(cleaned)
    if len(normalized.strip()) < 80:
        return None
    if _is_canned_fallback_answer(normalized):
        return None
    sections = _split_into_sections(normalized)
    if "Summary" not in sections:
        normalized = _ensure_required_sections(normalized, question, payload)
        sections = _split_into_sections(normalized)
        if "Summary" not in sections:
            return None
    if len([k for k, v in sections.items() if v]) < 2:
        normalized = _ensure_required_sections(normalized, question, payload)
    return normalized


def _try_groq_answer(
    question: str,
    payload: dict[str, Any],
    grounding: str,
    history: list[dict],
    api_key: str = "",
) -> str | None:
    """Try Groq with full then compact context — returns answer or None."""
    key = (api_key or GROQ_API_KEY).strip()
    if not key:
        logger.warning("GROQ_API_KEY not set — chat will use review-grounded fallback")
        return None

    topic = detect_topic(question)
    intent = detect_question_intent(question)
    evidence = _build_evidence_pack(question, payload, topic, intent)

    trimmed = grounding[:6000] if len(grounding) > 6000 else grounding
    attempts = [
        ("full", trimmed, False),
        ("compact", _compact_grounding_payload(payload, evidence=evidence), True),
    ]
    for label, ctx, compact in attempts:
        messages = _build_groq_messages(
            question, payload, ctx, history,
            evidence=evidence, compact=compact,
        )
        raw = _try_groq(messages, api_key=key)
        if not raw:
            logger.info("Groq %s attempt returned nothing for %r", label, question[:60])
            continue
        candidate = _accept_groq_answer(raw, question, payload)
        if candidate:
            logger.info("chat answer from Groq (%s) for %r", label, question[:60])
            return candidate
        logger.info("Groq %s answer rejected (structure) for %r", label, question[:60])
    return None


# ---------------------------------------------------------------------------
# Groq LLM path
# ---------------------------------------------------------------------------


def _groq_call(client, model: str, messages: list[dict]) -> str:
    def _run():
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=900,
            temperature=GROQ_TEMPERATURE,
        )
        return (resp.choices[0].message.content or "").strip()

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_run)
        try:
            return future.result(timeout=GROQ_TIMEOUT_SECONDS)
        except FuturesTimeout as exc:
            raise RuntimeError("groq_timeout") from exc


def _try_groq(messages: list[dict], api_key: str = "") -> str | None:
    key = (api_key or GROQ_API_KEY).strip()
    if not key:
        return None
    try:
        from groq import Groq
    except ImportError:
        return None

    client = Groq(api_key=key, timeout=GROQ_TIMEOUT_SECONDS + 3)

    seen: set[str] = set()
    for model in [GROQ_MODEL, GROQ_FALLBACK_MODEL]:
        if not model or model in seen:
            continue
        seen.add(model)
        try:
            text = _groq_call(client, model, messages)
            if text:
                return text
        except Exception as exc:
            logger.info("Groq model '%s' unavailable: %s", model, str(exc)[:200])
            continue
    return None


def _has_summary_only(text: str) -> bool:
    """Backwards-compat helper — Summary is the only hard requirement."""
    return "Summary" in _split_into_sections(text)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, request: Request) -> ChatResponse:
    groq_key = groq_api_key(request)
    try:
        payload, grounding, meta = build_review_context(req.question)
    except Exception as exc:
        logger.exception("context build failed: %s", exc)
        return ChatResponse(
            answer=(
                "## Summary\n\nThe review dataset is loading. Please retry your question in a moment.\n\n"
                "## Recommended Actions\n\n- Refresh and resend the same question once the dashboard finishes loading."
            ),
            grounding_size_chars=0,
            matched_reviews=0,
        )

    history = _trim_history(req.history, req.question)

    if CHAT_STABLE_MODE:
        answer = _build_data_grounded_answer(req.question, payload)
    else:
        answer = _try_groq_answer(
            req.question, payload, grounding, history=[], api_key=groq_key
        )
        if not answer:
            logger.info("chat answer from review-grounded fallback for %r", req.question[:80])
            answer = _build_data_grounded_answer(req.question, payload)

    answer = _ensure_required_sections(answer, req.question, payload)
    answer = _strip_ids_and_quotes(answer)

    return ChatResponse(
        answer=answer,
        grounding_size_chars=len(grounding),
        matched_reviews=int(meta.get("keyword_matches", 0))
        + int(meta.get("semantic_matches", 0)),
    )


@router.post("/ask", response_model=ChatResponse)
def ask(req: ChatRequest, request: Request) -> ChatResponse:
    """Alias for /chat — used by the discovery search bar."""
    return chat(req, request)
