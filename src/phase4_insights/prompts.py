"""LLM prompt templates for PM-ready insight card synthesis."""

from __future__ import annotations

from .aggregator import pain_to_theme
from .schemas import Severity, TopicBundle, Trend


SYSTEM_PROMPT = """You are a senior product manager at Spotify synthesizing user feedback
into actionable insight cards for the Discovery & Recommendations team.

You MUST:
- Output strict JSON only — no markdown, no commentary.
- Ground every claim in the evidence quotes provided.
- Write for a PM audience: specific, neutral, evidence-backed.
- Never invent statistics — use the numbers given.
- Suggest realistic product opportunities, not vague platitudes.
""".strip()


def _fmt_breakdown(d: dict, total: int) -> str:
    if not d:
        return "(none)"
    parts = [f"{k}: {v} ({100*v//max(1,total)}%)" for k, v in list(d.items())[:6]]
    return ", ".join(parts)


def build_user_prompt(bundle: TopicBundle, priority_score: float) -> str:
    quotes_block = "\n".join(f'  - "{q}"' for q in bundle.evidence_quotes[:8])
    needs_block = "\n".join(f"  - {n}" for n in bundle.unmet_needs[:6]) or "  - (none extracted)"
    severities = ", ".join(f'"{s.value}"' for s in Severity)
    trends = ", ".join(f'"{t.value}"' for t in Trend)

    return f"""Synthesize ONE insight card for this user-feedback cluster.

CLUSTER METADATA:
  topic_id: {bundle.topic_id}
  working_label: {bundle.label}
  supporting_review_count: {bundle.size}
  share_of_clustered_reviews_pct: {bundle.share_pct}
  discovery_related_pct: {bundle.discovery_share_pct}
  negative_sentiment_pct: {bundle.negative_share_pct}
  computed_priority_score: {priority_score}
  trend_signal: {bundle.trend.value} ({bundle.trend_detail})
  top_pain_category: {bundle.top_pain_category}
  theme_hint: {pain_to_theme(bundle.top_pain_category)}
  keywords: {", ".join(bundle.keywords[:8])}
  top_sources: {", ".join(bundle.top_sources)}

DISTRIBUTIONS (count in cluster={bundle.size}):
  sentiment: {_fmt_breakdown(bundle.sentiment_breakdown, bundle.size)}
  segment: {_fmt_breakdown(bundle.segment_breakdown, bundle.size)}
  pain_category: {_fmt_breakdown(bundle.pain_breakdown, bundle.size)}

TOP UNMET NEEDS (from Phase-2 extraction):
{needs_block}

EVIDENCE QUOTES (verbatim — cite these):
{quotes_block}

Return a JSON object with EXACTLY these keys:
{{
  "title": "<specific 6-12 word headline a PM can paste into a roadmap doc>",
  "theme": "<one of: Music Discovery, Recommendation Quality, Listening Behavior, Audio Quality, UI / UX, Pricing & Plans, Advertising, Technical Reliability, Content Availability, Podcasts, Social Features, General Feedback, Other>",
  "narrative": "<2-3 sentences summarizing the pain/opportunity with evidence>",
  "severity": "<one of: {severities}>",
  "trend": "<one of: {trends}>",
  "affected_segments": ["<segment names inferred from distribution, e.g. premium, heavy, unknown>"],
  "top_unmet_needs": ["<up to 5 distinct feature requests>"],
  "suggested_opportunity": "<one concrete product idea Spotify could pursue>",
  "segment_notes": "<optional 1 sentence on segment differences, or null>"
}}

Use severity/trend enums exactly as listed. Prefer the computed trend_signal unless quotes strongly contradict it.
""".strip()
