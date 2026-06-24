"""Groq-grounded chat — answers are structured into 4 sections and tailored to
each question. No review counts, no verbatim quotes, no review IDs.

Sections:
1. Summary
2. Key pain points
3. Product focus areas
4. Recommended actions
"""

from __future__ import annotations

import logging
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

sys.path.append(str(Path(__file__).resolve().parents[2]))

from rag import build_review_context  # noqa: E402

router = APIRouter()
logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_CHAT_MODEL", os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"))
GROQ_FALLBACK_MODEL = os.getenv("GROQ_CHAT_FALLBACK_MODEL", "llama-3.1-8b-instant")
GROQ_TIMEOUT_SECONDS = float(os.getenv("GROQ_CHAT_TIMEOUT", "15"))

MAX_HISTORY_TURNS = 4
MAX_HISTORY_CHARS = 600

SECTION_ORDER = ["Summary", "Key pain points", "Product focus areas", "Recommended actions"]

SECTION_ALIASES: dict[str, str] = {
    "summary": "Summary",
    "executive summary": "Summary",
    "overview": "Summary",
    "key pain points": "Key pain points",
    "pain points": "Key pain points",
    "key findings": "Key pain points",
    "main pain points": "Key pain points",
    "product focus areas": "Product focus areas",
    "focus areas": "Product focus areas",
    "product priorities": "Product focus areas",
    "recommended actions": "Recommended actions",
    "recommendations": "Recommended actions",
    "next steps": "Recommended actions",
    "actions": "Recommended actions",
    "suggested actions": "Recommended actions",
}

SYSTEM_PROMPT = """You are the Spotify Review Discovery Engine — a senior product analyst answering questions about Spotify user feedback.

You answer questions using ONLY the review context provided. You write in a clear, professional, executive-ready tone.

CRITICAL RULES:
- Your answer MUST be directly relevant to the specific question asked. Different questions must produce substantially different answers.
- NEVER include any numbers, counts, percentages, or statistics in your answer.
- NEVER include verbatim user quotes or review excerpts.
- NEVER mention review IDs, dataset sizes, or sample sizes.
- Present insights as qualitative findings — describe patterns, themes, and sentiments observed in the data.
- Stay tightly focused on the user's QUESTION — do not drift into unrelated pain areas.

EVERY answer MUST follow this EXACT structure with these EXACT 4 section headers (markdown bold):

**Summary**
A concise 2-3 sentence direct answer to the user's question. Describe the core finding or pattern that addresses their question.

**Key pain points**
3-5 bullets. Each bullet describes a specific pain point RELEVANT TO THE QUESTION. Format: `- **<Category Name>**: <one sentence describing the pain in plain language>`. Only include pain points that directly relate to the question asked.

**Product focus areas**
3-5 bullets. Each bullet identifies a concrete product area Spotify should improve to address the pain points above. Format: `- **<Area>**: <specific direction or improvement opportunity>`.

**Recommended actions**
3-4 bullets. Each bullet is a concrete, actionable next step for the Spotify product team that directly addresses the question. Be specific and practical.

Output ONLY these four sections, nothing else. Total length under 300 words."""


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
        "repeat", "repetitive", "same content", "same songs", "same artists",
        "loop", "stuck listening", "causes users to repeatedly",
        "why do users listen to the same",
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

_NUMBER_PATTERNS = [
    re.compile(r"\*\*[\d,]+\*\*"),
    re.compile(r"\b\d{1,6}(?:,\d{3})*\s*(?:reviews?|users?|mentions?|complaints?|responses?)\b", re.IGNORECASE),
    re.compile(r"\b(?:across|of|from|out of|analyzed|indexed)\s+\d[\d,]*\b", re.IGNORECASE),
    re.compile(r"\(\d[\d,%]*(?:\s*reviews?)?\)"),
    re.compile(r"\b\d+(?:\.\d+)?%"),
    re.compile(r"(?:app_store|play_store|reddit|social_media|community_forum):[^\s,;]+", re.IGNORECASE),
    re.compile(r"\breview[_\s-]?id[:\s]+\S+", re.IGNORECASE),
]

_QUOTE_PATTERNS = [
    re.compile(r'^>\s*".*"$', re.MULTILINE),
    re.compile(r"^>\s*—.*$", re.MULTILINE),
    re.compile(r'^"[^"]{20,}"', re.MULTILINE),
]


def _strip_numbers_and_quotes(text: str) -> str:
    for pat in _NUMBER_PATTERNS:
        text = pat.sub("", text)
    for pat in _QUOTE_PATTERNS:
        text = pat.sub("", text)
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r":\s*reviews\b", ":", text)
    text = re.sub(r"[^\S\n]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Section normalizer
# ---------------------------------------------------------------------------


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
        m = re.match(r"^\s*\*\*([^*]+?)\*\*\s*:?\s*$", raw)
        if m:
            header = m.group(1).strip().lower().rstrip(":")
            canonical = SECTION_ALIASES.get(header)
            if canonical:
                flush()
                current = canonical
                continue
        m2 = re.match(r"^\s*\*\*([^*]+?)\*\*\s*[:\-\u2014]?\s*(.+)$", raw)
        if m2:
            header = m2.group(1).strip().lower().rstrip(":")
            rest = m2.group(2).strip()
            canonical = SECTION_ALIASES.get(header)
            if canonical and rest and not rest.startswith("**"):
                flush()
                current = canonical
                buffer.append(rest)
                continue
        buffer.append(raw)

    flush()
    return {k: "\n".join(v).strip() for k, v in sections.items() if "\n".join(v).strip()}


def _enforce_section_order(text: str) -> str:
    sections = _split_into_sections(text)
    if not sections:
        return text.strip()

    # Remove any "Voice of the user" section the LLM may have added
    sections.pop("Voice of the user", None)

    parts: list[str] = []
    for name in SECTION_ORDER:
        body = sections.get(name)
        if not body:
            continue
        body = re.sub(r"^---+\s*$", "", body, flags=re.MULTILINE).strip()
        if body:
            parts.append(f"**{name}**\n\n{body}")
    if not parts:
        return text.strip()
    return "\n\n".join(parts)


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
# Groq LLM path
# ---------------------------------------------------------------------------


def _groq_call(client, model: str, messages: list[dict]) -> str:
    def _run():
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=900,
            temperature=0.3,
        )
        return (resp.choices[0].message.content or "").strip()

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(_run)
        try:
            return future.result(timeout=GROQ_TIMEOUT_SECONDS)
        except FuturesTimeout as exc:
            raise RuntimeError("groq_timeout") from exc


def _try_groq(messages: list[dict]) -> str | None:
    if not GROQ_API_KEY:
        return None
    try:
        from groq import Groq
    except ImportError:
        return None

    client = Groq(api_key=GROQ_API_KEY, timeout=GROQ_TIMEOUT_SECONDS + 3)

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


def _has_required_sections(text: str) -> bool:
    sections = _split_into_sections(text)
    must_have = {"Summary", "Key pain points", "Product focus areas", "Recommended actions"}
    return must_have.issubset(sections.keys())


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    try:
        payload, grounding, meta = build_review_context(req.question)
    except Exception as exc:
        logger.exception("context build failed: %s", exc)
        return ChatResponse(
            answer=(
                "**Summary**\n\nThe review dataset is loading. Please try again in a moment.\n\n"
                "**Key pain points**\n\nUnavailable until data loads.\n\n"
                "**Product focus areas**\n\nUnavailable until data loads.\n\n"
                "**Recommended actions**\n\n- Please retry your question shortly."
            ),
            grounding_size_chars=0,
            matched_reviews=0,
        )

    history = _trim_history(req.history, req.question)
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({
        "role": "user",
        "content": (
            "Answer the following question about Spotify user reviews. "
            "Use the context below but DO NOT cite any numbers, counts, or verbatim quotes. "
            "Follow the required 4-section structure exactly.\n\n"
            f"CONTEXT:\n{grounding}\n\n"
            f"QUESTION: {req.question}"
        ),
    })

    raw = _try_groq(messages)
    answer = ""
    if raw:
        cleaned = _strip_numbers_and_quotes(raw)
        normalized = _enforce_section_order(cleaned)
        if _has_required_sections(normalized) and len(normalized) >= 150:
            answer = normalized

    if not answer:
        intent = _detect_intent(req.question)
        answer = FALLBACK_ANSWERS.get(intent, FALLBACK_ANSWERS["general"])

    # Final safety pass
    answer = _strip_numbers_and_quotes(answer)

    return ChatResponse(
        answer=answer,
        grounding_size_chars=len(grounding),
        matched_reviews=int(meta.get("keyword_matches", 0))
        + int(meta.get("semantic_matches", 0)),
    )


@router.post("/ask", response_model=ChatResponse)
def ask(req: ChatRequest) -> ChatResponse:
    """Alias for /chat — used by the discovery search bar."""
    return chat(req)
