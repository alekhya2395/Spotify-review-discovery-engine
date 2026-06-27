"""Deterministic Review Analysis Workflow Engine.

Flow:
  User Question → Query Classification → Insight Cluster → Structured Answer

No LLM rewriting. Same question → same answer every time.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from query_classifier import (
    CATEGORY_LABELS,
    OUT_OF_SCOPE_MESSAGE,
    classify_query,
)

CLUSTERS_DIR = Path(__file__).resolve().parent / "data" / "insight_clusters"

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


@lru_cache(maxsize=1)
def _load_all_clusters() -> dict[str, dict[str, Any]]:
    clusters: dict[str, dict[str, Any]] = {}
    if not CLUSTERS_DIR.is_dir():
        return clusters
    for path in sorted(CLUSTERS_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        cat = payload.get("category") or path.stem
        clusters[str(cat)] = payload
    return clusters


def load_cluster(category_id: str) -> dict[str, Any] | None:
    return _load_all_clusters().get(category_id)


def _analysis_header(category_id: str, category_label: str, confidence: str) -> str:
    return (
        "**Analysis Type:**\n"
        "✓ Validated Review Analysis\n\n"
        f"**Category:**\n{category_label}\n\n"
        f"**Confidence:**\n{confidence}\n"
    )


def _bullets(items: list[str]) -> str:
    lines = [f"- {str(item).rstrip('.')}." for item in items if str(item).strip()]
    return "\n".join(lines) if lines else "- No additional items in this category for the current dataset."


def _render_evidence(cluster: dict[str, Any]) -> str:
    total = cluster.get("total_reviews_analyzed") or 0
    disc = cluster.get("discovery_related_reviews") or 0
    disc_share = cluster.get("discovery_related_share") or ""

    lines = [
        f"**Total Reviews Analyzed:** {total:,}",
    ]
    if disc:
        suffix = f" ({disc_share})" if disc_share else ""
        lines.append(f"**Discovery-Related Reviews:** {disc:,}{suffix}")
    lines.append("")

    evidence = cluster.get("evidence") or []
    if not evidence:
        lines.append("- Insufficient clustered evidence above the minimum review threshold.")
        return "\n".join(lines)

    for item in evidence[:8]:
        label = item.get("label") or "Finding"
        count = int(item.get("count") or 0)
        pct = item.get("percentage") or ""
        pool = item.get("pool") or "of analyzed reviews"
        conf = item.get("confidence") or cluster.get("overall_confidence") or "Medium"
        support = item.get("support_line") or f"{count:,} reviews in the analyzed corpus"
        pct_part = f" ({pct} {pool})" if pct else ""
        lines.append(f"- **{label}** — {count:,} reviews{pct_part}")
        lines.append(f"  - **Confidence:** {conf}")
        lines.append(f"  - **Supported by:** {support}")
    return "\n".join(lines)


def _question_hook(question: str, category_id: str) -> str:
    """One-line opener tying the cluster summary to the exact question."""
    q = question.strip().rstrip("?")
    label = CATEGORY_LABELS.get(category_id, category_id.replace("_", " ").title())
    return f"Regarding your question — *{q}* — the validated **{label}** cluster shows:"


def render_cluster_answer(question: str, cluster: dict[str, Any], category_id: str) -> str:
    """Render the mandatory 8-section evaluation format."""
    category_label = cluster.get("title") or CATEGORY_LABELS.get(category_id, category_id)
    confidence = cluster.get("overall_confidence") or "Medium"

    parts = [
        _analysis_header(category_id, category_label, confidence),
        f"## Summary\n\n{_question_hook(question, category_id)} {cluster.get('summary', '').strip()}",
        f"## Evidence\n\n{_render_evidence(cluster)}",
        f"## Key Pain Points\n\n{_bullets(cluster.get('key_pain_points') or [])}",
        f"## Root Causes\n\n{_bullets(cluster.get('root_causes') or [])}",
        f"## Affected User Segments\n\n{_bullets(cluster.get('affected_segments') or [])}",
        f"## Unmet Needs\n\n{_bullets(cluster.get('unmet_needs') or [])}",
        f"## Product Focus Areas\n\n{_bullets(cluster.get('product_focus_areas') or [])}",
        f"## Recommended Actions\n\n{_bullets(cluster.get('recommended_actions') or [])}",
    ]
    return "\n\n".join(parts)


def generate_workflow_answer(question: str) -> dict[str, Any]:
    """Main entry: classify → cluster → deterministic markdown answer."""
    category_id, score, category_label = classify_query(question)

    if not category_id:
        return {
            "answer": OUT_OF_SCOPE_MESSAGE,
            "answer_mode": "out_of_scope",
            "category": None,
            "category_label": "",
            "confidence": "Low",
            "classification_score": score,
        }

    cluster = load_cluster(category_id)
    if not cluster:
        return {
            "answer": (
                "Insight cluster data is not available. "
                "Run `python scripts/build_insight_clusters.py` to generate validated clusters."
            ),
            "answer_mode": "error",
            "category": category_id,
            "category_label": category_label,
            "confidence": "Low",
            "classification_score": score,
        }

    answer = render_cluster_answer(question, cluster, category_id)
    return {
        "answer": answer,
        "answer_mode": "deterministic",
        "category": category_id,
        "category_label": category_label,
        "confidence": cluster.get("overall_confidence") or "Medium",
        "classification_score": score,
    }


__all__ = ["generate_workflow_answer", "load_cluster", "render_cluster_answer"]
