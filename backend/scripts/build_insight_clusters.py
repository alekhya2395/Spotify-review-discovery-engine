"""Build validated insight-cluster JSON files from the analyzed review corpus.

Run once after data refresh:
    python scripts/build_insight_clusters.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from confidence import compute_confidence, format_support_line  # noqa: E402
from data_loader import load_insights_df  # noqa: E402
from discovery_insights import compute_discovery_insights  # noqa: E402
from query_classifier import CATEGORY_LABELS  # noqa: E402
from root_causes import compute_root_causes  # noqa: E402
from unmet_need_inference import strategic_rewrite  # noqa: E402
from user_segments import compute_user_segments  # noqa: E402

OUT_DIR = BACKEND / "data" / "insight_clusters"

_GENERIC_LABELS = {"Other discovery-related signal", "Other discovery struggle (uncategorised)"}


def _conf(count: int, share: str = "", sources: dict | None = None) -> dict[str, str]:
    c = compute_confidence(count, share=share, source_counts=sources or {})
    return {"level": c["level"], "support_line": c["support_line"]}


def _evidence_item(
    label: str,
    count: int,
    percentage: str,
    pool: str,
    sources: dict | None = None,
) -> dict[str, Any]:
    conf = _conf(count, share=percentage, sources=sources)
    return {
        "label": label,
        "count": count,
        "percentage": percentage,
        "pool": pool,
        "confidence": conf["level"],
        "support_line": conf["support_line"],
    }


def _groups_to_evidence(groups: list[dict], pool_label: str, limit: int = 6) -> list[dict]:
    out: list[dict] = []
    for g in groups:
        label = g.get("label") or ""
        if not label or label in _GENERIC_LABELS or label.startswith("Other"):
            continue
        count = int(g.get("count") or 0)
        if count < 10:
            continue
        pct = g.get("share_of_pool") or g.get("share_of_corpus") or ""
        out.append(_evidence_item(label, count, pct, pool_label, g.get("source_counts")))
        if len(out) >= limit:
            break
    return out


def _segments_payload(segments: list[dict], limit: int = 6) -> list[dict]:
    rows: list[dict] = []
    for seg in segments[:limit]:
        name = seg.get("name") or ""
        dc = (seg.get("discovery_challenge") or {}).get("label") or ""
        pf = (seg.get("primary_frustration") or {}).get("label") or ""
        un = (seg.get("unmet_need") or {}).get("label") or ""
        rows.append({
            "segment": name,
            "count": seg.get("count"),
            "share_of_corpus": seg.get("share_of_corpus"),
            "discovery_challenge": dc,
            "primary_frustration": pf,
            "unmet_need": strategic_rewrite(un) if un else "",
        })
    return rows


def _overall_confidence(evidence: list[dict]) -> str:
    if not evidence:
        return "Medium"
    levels = [e.get("confidence") for e in evidence]
    if levels.count("High") >= 2:
        return "High"
    if "High" in levels:
        return "High"
    if "Medium" in levels:
        return "Medium"
    return "Low"


def _pain_bullets(items: list[dict], field: str = "label") -> list[str]:
    return [str(i.get(field) or "").strip() for i in items if i.get(field)][:5]


def _cause_bullets(causes: list[dict], limit: int = 5) -> list[str]:
    return [
        f"{c['label']}: {c.get('summary', '').rstrip('.')}"
        for c in causes[:limit]
        if c.get("label")
    ]


def _segment_bullets(segments: list[dict]) -> list[str]:
    lines: list[str] = []
    for s in segments:
        name = s.get("segment") or s.get("name") or ""
        dc = s.get("discovery_challenge") or ""
        pf = s.get("primary_frustration") or ""
        bit = dc or pf
        if name and bit:
            lines.append(f"{name}: {bit}")
    return lines[:6]


def _unmet_bullets(groups: list[dict]) -> list[str]:
    out: list[str] = []
    for g in groups:
        label = g.get("label") or ""
        if not label or label.startswith("Other"):
            continue
        out.append(strategic_rewrite(label) if not label.startswith("Need") else label)
        if len(out) >= 5:
            break
    return out


def _actions_for(category: str) -> list[str]:
    actions: dict[str, list[str]] = {
        "music_discovery_challenges": [
            "Launch a dedicated Explore surface outside the taste bubble with genre and mood bridges.",
            "Add user-facing discovery intensity controls tied to recommendation novelty.",
            "Instrument discovery funnels to measure first-time artist exposure per session.",
        ],
        "repetitive_listening_behavior": [
            "Penalize recently played tracks in autoplay and radio with configurable freshness windows.",
            "Surface explicit break-the-loop prompts when repetition thresholds are exceeded.",
            "Audit engagement loops that overweight repeat plays as strong preference signals.",
        ],
        "playlist_dependency": [
            "Diversify discovery paths beyond Discover Weekly, Release Radar, and Daily Mix.",
            "Refresh curated playlists on shorter cycles with transparent update signals.",
            "Offer alternative discovery modes for users who only engage through playlists.",
        ],
        "recommendation_quality": [
            "Improve negative feedback loops so skips and dislikes reshape future mixes faster.",
            "Separate casual listening signals from durable taste signals in ranking.",
            "Run periodic recommendation audits segmented by listening style.",
        ],
        "user_segments": [
            "Tailor discovery surfaces by segment: seekers vs. playlist-first vs. free-tier explorers.",
            "Compare segment-level frustration rates in quarterly discovery health reviews.",
            "Pilot segment-specific onboarding that routes users to appropriate discovery tools.",
        ],
        "discovery_frustrations": [
            "Reduce friction in the first three taps from home to unfamiliar music.",
            "Address top frustration themes with targeted UX and algorithm fixes.",
            "Publish a discovery changelog when major recommendation behavior changes ship.",
        ],
        "unmet_needs": [
            "Prioritize the top three strategic unmet needs with measurable success metrics.",
            "Validate unmet-need clusters with follow-up in-product micro-surveys.",
            "Map each unmet need to a concrete product bet and owner team.",
        ],
        "root_causes": [
            "Fix systemic causes (over-personalization, weak exploration tools) before surface tweaks.",
            "Assign owners to the top root-cause categories with OKRs tied to review sentiment.",
            "Run root-cause reviews when discovery NPS or complaint volume shifts.",
        ],
        "discovery_journeys": [
            "Map end-to-end discovery journeys and remove dead-end paths in search and home.",
            "Add journey-aware prompts at high-intent moments (search, save, skip).",
            "Measure time-to-first-new-artist as a core discovery KPI.",
        ],
        "product_opportunities": [
            "Rank opportunities by review volume, segment impact, and feasibility.",
            "Fund two discovery bets per quarter with pre-defined success metrics.",
            "Close the loop with users when shipped features address top review themes.",
        ],
        "ai_assisted_discovery": [
            "Use AI to explain why a track was recommended and offer one-click alternatives.",
            "Combine collaborative filtering with explicit exploration objectives in ranking.",
            "Pilot conversational discovery that stays grounded in catalog and user history.",
        ],
    }
    return actions.get(category, actions["product_opportunities"])


def _focus_for(category: str) -> list[str]:
    focus: dict[str, list[str]] = {
        "music_discovery_challenges": [
            "Dedicated exploration surfaces beyond personalized home feeds",
            "Guided discovery for unfamiliar genres and emerging artists",
            "Clearer paths from search intent to new artist pages",
        ],
        "repetitive_listening_behavior": [
            "Freshness controls in autoplay, shuffle, and radio",
            "Anti-repetition guardrails in recommendation ranking",
            "Transparency when the algorithm re-surfaces known favorites",
        ],
        "playlist_dependency": [
            "Alternative discovery channels independent of curated playlists",
            "Playlist refresh and diversity metrics visible to users",
            "Cross-surface discovery that does not require playlist entry",
        ],
        "recommendation_quality": [
            "Feedback-responsive personalization",
            "Taste-profile transparency and user correction tools",
            "Quality benchmarks for Discover Weekly and Release Radar",
        ],
        "user_segments": [
            "Segment-aware discovery defaults and onboarding",
            "Free-tier discovery experience without ad-driven interruption",
            "Power-listener tools for intentional exploration",
        ],
        "discovery_frustrations": [
            "Reduce stale and irrelevant recommendation moments",
            "Fix discovery UX friction points surfaced in negative reviews",
            "Restore trust in Discover Weekly and algorithmic mixes",
        ],
        "unmet_needs": [
            "Strategic needs over feature requests (motivation-first roadmap)",
            "Regional and niche-genre discovery coverage",
            "Balanced familiarity–novelty in recommendations",
        ],
        "root_causes": [
            "Over-personalization and echo-chamber dynamics",
            "Weak exploration tooling and controls",
            "Playlist and engagement-loop dependencies",
        ],
        "discovery_journeys": [
            "Onboarding paths into first meaningful discovery win",
            "Context-aware discovery (mood, activity, social)",
            "Seamless transitions from search to sustained exploration",
        ],
        "product_opportunities": [
            "High-impact discovery bets ranked by review evidence",
            "Monetization aligned with exploration (not interruption)",
            "Social and curator-led discovery extensions",
        ],
        "ai_assisted_discovery": [
            "Explainable AI recommendations with user steering",
            "Exploration objectives alongside personalization in ranking",
            "Grounded conversational discovery assistants",
        ],
    }
    return focus.get(category, focus["product_opportunities"])


def build_all() -> dict[str, dict[str, Any]]:
    df = load_insights_df()
    total = int(len(df))
    discovery_total = int(df["is_discovery_related"].sum()) if "is_discovery_related" in df.columns else 0
    discovery_share = f"{round(100.0 * discovery_total / total, 1)}%" if total else ""

    di = compute_discovery_insights()
    rc = compute_root_causes()
    us = compute_user_segments()
    segments = us.get("segments") or []
    causes = rc.get("causes") or []

    base_meta = {
        "total_reviews_analyzed": total,
        "discovery_related_reviews": discovery_total,
        "discovery_related_share": discovery_share,
    }

    clusters: dict[str, dict[str, Any]] = {}

    # --- music_discovery_challenges ---
    struggles = di.get("discovery_struggles", {}).get("groups") or []
    ev = _groups_to_evidence(struggles, "discovery-related")
    seg = _segments_payload(segments)
    clusters["music_discovery_challenges"] = {
        **base_meta,
        "category": "music_discovery_challenges",
        "title": CATEGORY_LABELS["music_discovery_challenges"],
        "summary": (
            "Users struggle to discover new music because algorithmic feeds reinforce existing "
            "tastes, exploration beyond playlists is limited, and paths to unfamiliar artists "
            "and genres are unclear."
        ),
        "evidence": ev,
        "key_pain_points": _pain_bullets(ev),
        "root_causes": _cause_bullets([c for c in causes if c["label"] in {
            "Weak exploration tools", "Over-personalization", "Playlist dependency",
        }]),
        "affected_segments": _segment_bullets(seg),
        "unmet_needs": _unmet_bullets(di.get("discovery_unmet_needs", {}).get("groups") or []),
        "product_focus_areas": _focus_for("music_discovery_challenges"),
        "recommended_actions": _actions_for("music_discovery_challenges"),
        "overall_confidence": _overall_confidence(ev),
    }

    # --- repetitive_listening_behavior ---
    rep = di.get("repetition_causes", {}).get("groups") or []
    ev = _groups_to_evidence(rep, "repetition-related")
    clusters["repetitive_listening_behavior"] = {
        **base_meta,
        "category": "repetitive_listening_behavior",
        "title": CATEGORY_LABELS["repetitive_listening_behavior"],
        "summary": (
            "Repetitive listening is driven by recommendation loops that resurface favorites, "
            "shuffle and autoplay lacking freshness, and engagement signals that overweight repeat plays."
        ),
        "evidence": ev,
        "key_pain_points": _pain_bullets(ev),
        "root_causes": _cause_bullets([c for c in causes if c["label"] in {
            "Over-personalization", "Genre repetition", "Feedback signals don't tune the algorithm",
        }]),
        "affected_segments": _segment_bullets(seg),
        "unmet_needs": ["Need more diverse recommendations", "Need smarter shuffle and autoplay"],
        "product_focus_areas": _focus_for("repetitive_listening_behavior"),
        "recommended_actions": _actions_for("repetitive_listening_behavior"),
        "overall_confidence": _overall_confidence(ev),
    }

    # --- playlist_dependency ---
    playlist_ev = [
        e for e in _groups_to_evidence(struggles + rep, "discovery-related")
        if any(k in (e.get("label") or "").lower() for k in (
            "discover weekly", "release radar", "playlist", "curated", "daily mix",
        ))
    ] or _groups_to_evidence(struggles, "discovery-related")[:3]
    clusters["playlist_dependency"] = {
        **base_meta,
        "category": "playlist_dependency",
        "title": CATEGORY_LABELS["playlist_dependency"],
        "summary": (
            "Many users depend on Discover Weekly, Release Radar, and Daily Mix as their "
            "primary discovery channel, leaving few alternatives when those playlists feel stale."
        ),
        "evidence": playlist_ev,
        "key_pain_points": _pain_bullets(playlist_ev),
        "root_causes": _cause_bullets([c for c in causes if c["label"] == "Playlist dependency"]),
        "affected_segments": _segment_bullets([s for s in seg if s["segment"] == "Playlist User"] or seg),
        "unmet_needs": ["Need stronger curated discovery playlists", "Need dedicated discovery surfaces beyond Discover Weekly"],
        "product_focus_areas": _focus_for("playlist_dependency"),
        "recommended_actions": _actions_for("playlist_dependency"),
        "overall_confidence": _overall_confidence(playlist_ev),
    }

    # --- recommendation_quality ---
    frust = di.get("discovery_frustrations", {}).get("groups") or []
    ev = _groups_to_evidence(frust, "negative discovery feedback")
    clusters["recommendation_quality"] = {
        **base_meta,
        "category": "recommendation_quality",
        "title": CATEGORY_LABELS["recommendation_quality"],
        "summary": (
            "Recommendation quality suffers when suggestions feel stale, irrelevant, or "
            "misaligned with taste — users report the algorithm missing context from skips and dislikes."
        ),
        "evidence": ev,
        "key_pain_points": _pain_bullets(ev),
        "root_causes": _cause_bullets([c for c in causes if c["label"] in {
            "Over-personalization", "Feedback signals don't tune the algorithm", "Mainstream bias",
        }]),
        "affected_segments": _segment_bullets(seg),
        "unmet_needs": ["Need better personalization", "Need fresher and more accurate recommendations"],
        "product_focus_areas": _focus_for("recommendation_quality"),
        "recommended_actions": _actions_for("recommendation_quality"),
        "overall_confidence": _overall_confidence(ev),
    }
    clusters["recommendation_quality"]["title"] = CATEGORY_LABELS["recommendation_quality"]

    # --- user_segments ---
    seg_ev: list[dict] = []
    for s in segments:
        count = int(s.get("count") or 0)
        if count < 10:
            continue
        seg_ev.append(_evidence_item(
            f"{s['name']} segment reviews",
            count,
            s.get("share_of_corpus") or "",
            "of total",
            None,
        ))
    clusters["user_segments"] = {
        **base_meta,
        "category": "user_segments",
        "title": CATEGORY_LABELS["user_segments"],
        "summary": (
            "Discovery challenges differ by segment: Discovery Seekers struggle to find new artists; "
            "Playlist Users depend on stale curated feeds; Free Users face ad disruption during "
            "exploration; Heavy and Casual listeners show distinct frustration patterns."
        ),
        "evidence": seg_ev[:6],
        "key_pain_points": [f"{s['segment']}: {s.get('primary_frustration') or s.get('discovery_challenge')}" for s in seg if s.get("segment")][:5],
        "root_causes": _cause_bullets(causes[:4]),
        "affected_segments": _segment_bullets(seg),
        "unmet_needs": [
            strategic_rewrite((s.get("unmet_need") or {}).get("label", ""))
            for s in segments
            if (s.get("unmet_need") or {}).get("label")
        ][:5],
        "product_focus_areas": _focus_for("user_segments"),
        "recommended_actions": _actions_for("user_segments"),
        "overall_confidence": _overall_confidence(seg_ev),
    }
    clusters["user_segments"]["unmet_needs"] = [
        s["unmet_need"] for s in seg
        if s.get("unmet_need") and s["unmet_need"] != "Need a more reliable music experience"
    ][:5]

    # --- discovery_frustrations ---
    ev = _groups_to_evidence(frust, "negative discovery feedback")
    clusters["discovery_frustrations"] = {
        **base_meta,
        "category": "discovery_frustrations",
        "title": CATEGORY_LABELS["discovery_frustrations"],
        "summary": (
            "Discovery frustrations cluster around stale recommendations, algorithm mistrust, "
            "Discover Weekly disappointment, and ads interrupting active exploration."
        ),
        "evidence": ev,
        "key_pain_points": _pain_bullets(ev),
        "root_causes": _cause_bullets(causes[:5]),
        "affected_segments": _segment_bullets(seg),
        "unmet_needs": _unmet_bullets(di.get("discovery_unmet_needs", {}).get("groups") or []),
        "product_focus_areas": _focus_for("discovery_frustrations"),
        "recommended_actions": _actions_for("discovery_frustrations"),
        "overall_confidence": _overall_confidence(ev),
    }

    # --- unmet_needs ---
    unmet_groups = di.get("discovery_unmet_needs", {}).get("groups") or []
    ev = _groups_to_evidence(unmet_groups, "discovery-related")
    clusters["unmet_needs"] = {
        **base_meta,
        "category": "unmet_needs",
        "title": CATEGORY_LABELS["unmet_needs"],
        "summary": (
            "Reviews consistently surface strategic unmet needs: easier discovery, fresher "
            "recommendations, stronger curated playlists, and control over algorithmic novelty."
        ),
        "evidence": ev,
        "key_pain_points": _unmet_bullets(unmet_groups),
        "root_causes": _cause_bullets(causes[:4]),
        "affected_segments": _segment_bullets(seg),
        "unmet_needs": _unmet_bullets(unmet_groups),
        "product_focus_areas": _focus_for("unmet_needs"),
        "recommended_actions": _actions_for("unmet_needs"),
        "overall_confidence": _overall_confidence(ev),
    }

    # --- root_causes ---
    ev = []
    for c in causes[:6]:
        count = int(c.get("count") or 0)
        if count < 10:
            continue
        ev.append(_evidence_item(
            c["label"], count, c.get("share_of_corpus") or "", "of total", c.get("source_counts"),
        ))
    clusters["root_causes"] = {
        **base_meta,
        "category": "root_causes",
        "title": CATEGORY_LABELS["root_causes"],
        "summary": (
            "Root causes behind discovery problems include weak exploration tools, "
            "over-personalization, playlist dependency, ad disruption on the free tier, "
            "and feedback signals that fail to tune recommendations."
        ),
        "evidence": ev,
        "key_pain_points": [c["label"] for c in causes[:5]],
        "root_causes": _cause_bullets(causes[:6]),
        "affected_segments": _segment_bullets(seg),
        "unmet_needs": _unmet_bullets(unmet_groups),
        "product_focus_areas": _focus_for("root_causes"),
        "recommended_actions": _actions_for("root_causes"),
        "overall_confidence": _overall_confidence(ev),
    }

    # --- discovery_journeys ---
    journey_ev = _groups_to_evidence(struggles + frust, "discovery-related")[:5]
    clusters["discovery_journeys"] = {
        **base_meta,
        "category": "discovery_journeys",
        "title": CATEGORY_LABELS["discovery_journeys"],
        "summary": (
            "Typical discovery journeys start from home or search, pass through playlists "
            "or radio, and often dead-end when users cannot escape their taste profile "
            "or find unfamiliar artists without curated playlist dependency."
        ),
        "evidence": journey_ev,
        "key_pain_points": _pain_bullets(journey_ev),
        "root_causes": _cause_bullets([c for c in causes if c["label"] in {
            "Weak exploration tools", "UI / navigation friction", "Playlist dependency",
        }]),
        "affected_segments": _segment_bullets(seg),
        "unmet_needs": _unmet_bullets(unmet_groups),
        "product_focus_areas": _focus_for("discovery_journeys"),
        "recommended_actions": _actions_for("discovery_journeys"),
        "overall_confidence": _overall_confidence(journey_ev),
    }

    # --- product_opportunities ---
    clusters["product_opportunities"] = {
        **base_meta,
        "category": "product_opportunities",
        "title": CATEGORY_LABELS["product_opportunities"],
        "summary": (
            "Highest-impact product opportunities align with review-backed themes: exploration "
            "surfaces outside the taste bubble, freshness controls, segment-aware discovery, "
            "and reducing ad-driven interruption for free-tier explorers."
        ),
        "evidence": ev[:4] if (ev := _groups_to_evidence(unmet_groups + struggles, "discovery-related")) else [],
        "key_pain_points": _focus_for("product_opportunities")[:3],
        "root_causes": _cause_bullets(causes[:3]),
        "affected_segments": _segment_bullets(seg),
        "unmet_needs": _unmet_bullets(unmet_groups),
        "product_focus_areas": _focus_for("product_opportunities"),
        "recommended_actions": _actions_for("product_opportunities"),
        "overall_confidence": _overall_confidence(ev[:4] if ev else []),
    }

    # --- ai_assisted_discovery ---
    ai_ev = [
        e for e in _groups_to_evidence(frust + struggles, "discovery-related")
        if any(k in (e.get("label") or "").lower() for k in (
            "algorithm", "personal", "recommend", "relevant", "control",
        ))
    ] or _groups_to_evidence(frust, "negative discovery feedback")[:4]
    clusters["ai_assisted_discovery"] = {
        **base_meta,
        "category": "ai_assisted_discovery",
        "title": CATEGORY_LABELS["ai_assisted_discovery"],
        "summary": (
            "AI-assisted discovery opportunities include explainable recommendations, "
            "exploration objectives in ranking, feedback-responsive personalization, "
            "and grounded discovery assistants that respect user taste boundaries."
        ),
        "evidence": ai_ev,
        "key_pain_points": _pain_bullets(ai_ev),
        "root_causes": _cause_bullets([c for c in causes if "personal" in c["label"].lower() or "Feedback" in c["label"]]),
        "affected_segments": _segment_bullets(seg),
        "unmet_needs": ["Need better personalization", "Need confidence when exploring new music"],
        "product_focus_areas": _focus_for("ai_assisted_discovery"),
        "recommended_actions": _actions_for("ai_assisted_discovery"),
        "overall_confidence": _overall_confidence(ai_ev),
    }

    for cluster in clusters.values():
        cluster["overall_confidence"] = cluster.get("overall_confidence") or "Medium"

    return clusters


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    clusters = build_all()
    for cat_id, payload in clusters.items():
        path = OUT_DIR / f"{cat_id}.json"
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Wrote {path.name} ({len(payload.get('evidence') or [])} evidence items)")


if __name__ == "__main__":
    main()
