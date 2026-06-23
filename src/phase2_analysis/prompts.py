"""LLM prompt templates for structured insight extraction.

The system prompt locks the LLM into the role of a senior product researcher.
The user prompt enumerates each review and asks for a strict JSON response
following our `Insight` schema. Field enums are spelled out in the prompt so
the LLM never invents a category.
"""

from __future__ import annotations

from typing import List

from .schemas import PainCategory, Segment, Sentiment


SYSTEM_PROMPT = """You are a senior product researcher on Spotify's Growth Team.

Your job is to read raw user feedback about Spotify (from app stores, Reddit,
community forums, social media) and extract structured, evidence-backed
insights about music discovery, recommendation quality, and user behavior.

You MUST:
- Output strict JSON only — no commentary, no markdown fences.
- Use exactly the enum values provided. Never invent new ones.
- Quote the user verbatim — never paraphrase the verbatim_quote field.
- If a field is unclear, prefer the conservative default ("none", "unknown")
  rather than guessing.
- Never include personally identifiable information beyond what the user
  already revealed in the review text.
""".strip()


def _enum_values(enum_cls) -> str:
    return ", ".join(f'"{m.value}"' for m in enum_cls)


USER_PROMPT_TEMPLATE = """Analyze the following {n} Spotify user reviews.

For EACH review, return one JSON object with these fields:

- "review_id"          : string (use the exact id provided)
- "discovery_related"  : boolean (true if review touches music discovery,
                         recommendations, exploration, repetitive listening,
                         Discover Weekly, Release Radar, algorithmic playlists,
                         finding new artists, mood/activity discovery, etc.)
- "pain_category"      : one of {pain_categories}
- "sentiment"          : one of {sentiments}
- "segment"            : one of {segments} (infer ONLY from explicit cues in
                         the review; otherwise "unknown")
- "unmet_need"         : short phrase (<= 25 words) describing the feature
                         request / missing capability, or "none"
- "verbatim_quote"     : the exact substring from the review text that best
                         supports the analysis (<= 50 words, copied character-
                         for-character; do not paraphrase)
- "confidence"         : float 0.0-1.0 (your confidence in this analysis)

Return a single JSON object with one key:

    {{"insights": [ <one insight object per review, in the same order> ]}}

REVIEWS:
{reviews_block}
""".strip()


def build_user_prompt(reviews: List[dict]) -> str:
    """Render the user prompt for a batch of reviews."""
    blocks = []
    for r in reviews:
        rid = r.get("review_id", "")
        source = r.get("source", "")
        rating = r.get("rating")
        rating_str = f" (rating={rating})" if rating is not None else ""
        text = (r.get("text") or "").strip().replace("\r", " ")
        if len(text) > 1500:
            text = text[:1500] + "..."
        blocks.append(
            f"--- REVIEW review_id={rid} source={source}{rating_str} ---\n{text}"
        )

    return USER_PROMPT_TEMPLATE.format(
        n=len(reviews),
        pain_categories=_enum_values(PainCategory),
        sentiments=_enum_values(Sentiment),
        segments=_enum_values(Segment),
        reviews_block="\n\n".join(blocks),
    )
