"""Insight card generator — Groq RAG synthesis + rule-based fallback."""

from __future__ import annotations

import json
from typing import List, Optional

from loguru import logger
from pydantic import ValidationError

from .aggregator import pain_to_theme
from .config import settings
from .prompts import SYSTEM_PROMPT, build_user_prompt
from .scorer import default_severity
from .schemas import InsightCard, Severity, TopicBundle, Trend


class CardGenerator:
    """Generate InsightCard objects from TopicBundle aggregates."""

    def __init__(self, use_llm: Optional[bool] = None, model: Optional[str] = None) -> None:
        self.use_llm = settings.use_llm_cards if use_llm is None else use_llm
        self.model = model or settings.groq_model
        self._client = None
        self._consecutive_failures = 0
        self._max_failures = 5

        if self.use_llm and not settings.groq_enabled():
            logger.warning("[generator] GROQ_API_KEY missing — using rule-based cards")
            self.use_llm = False

        if self.use_llm:
            try:
                from groq import Groq
                self._client = Groq(
                    api_key=settings.groq_api_key,
                    timeout=settings.request_timeout_seconds,
                )
                logger.info("[generator] LLM cards enabled (model={m})", m=self.model)
            except Exception as exc:
                logger.warning("[generator] Groq init failed ({e}) — rule-based fallback", e=exc)
                self.use_llm = False

    def generate_all(
        self,
        bundles: List[TopicBundle],
        priority_scores: dict[int, float],
    ) -> List[InsightCard]:
        cards: List[InsightCard] = []
        for idx, bundle in enumerate(bundles, start=1):
            score = priority_scores.get(bundle.topic_id, 0.0)
            insight_id = f"INS-{bundle.topic_id:03d}"
            try:
                card = self._generate_one(bundle, insight_id, score)
            except Exception as exc:
                logger.error(
                    "[generator] topic {t} failed ({e}) — rule-based fallback",
                    t=bundle.topic_id,
                    e=exc,
                )
                card = self._rule_based_card(bundle, insight_id, score)
            cards.append(card)
            logger.info(
                "[generator] {i}/{n} topic_id={t} -> {title}",
                i=idx,
                n=len(bundles),
                t=bundle.topic_id,
                title=card.title[:60],
            )
        return cards

    def _generate_one(
        self,
        bundle: TopicBundle,
        insight_id: str,
        priority_score: float,
    ) -> InsightCard:
        if not self.use_llm or self._client is None:
            return self._rule_based_card(bundle, insight_id, priority_score)

        if self._consecutive_failures >= self._max_failures:
            return self._rule_based_card(bundle, insight_id, priority_score)

        user_prompt = build_user_prompt(bundle, priority_score)
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=settings.groq_temperature,
                max_tokens=settings.groq_max_tokens,
                response_format={"type": "json_object"},
            )
            content = (resp.choices[0].message.content or "").strip()
            payload = json.loads(content)
            self._consecutive_failures = 0
            return self._validate_llm_card(payload, bundle, insight_id, priority_score)
        except Exception as exc:
            self._consecutive_failures += 1
            short = str(exc).splitlines()[0][:160]
            logger.warning("[generator] LLM failed topic {t}: {e}", t=bundle.topic_id, e=short)
            if self._consecutive_failures == self._max_failures:
                logger.warning(
                    "[generator] disabling LLM after {n} consecutive failures",
                    n=self._max_failures,
                )
            return self._rule_based_card(bundle, insight_id, priority_score)

    def _validate_llm_card(
        self,
        payload: dict,
        bundle: TopicBundle,
        insight_id: str,
        priority_score: float,
    ) -> InsightCard:
        data = {
            "insight_id": insight_id,
            "topic_id": bundle.topic_id,
            "title": payload.get("title") or bundle.label,
            "theme": payload.get("theme") or pain_to_theme(bundle.top_pain_category),
            "narrative": payload.get("narrative") or self._default_narrative(bundle),
            "severity": payload.get("severity") or default_severity(bundle).value,
            "trend": payload.get("trend") or bundle.trend.value,
            "priority_score": priority_score,
            "affected_segments": payload.get("affected_segments") or self._top_segments(bundle),
            "top_unmet_needs": payload.get("top_unmet_needs") or bundle.unmet_needs[:5],
            "evidence_quotes": bundle.evidence_quotes,
            "evidence_review_ids": bundle.evidence_review_ids,
            "supporting_review_count": bundle.size,
            "discovery_share_pct": bundle.discovery_share_pct,
            "negative_share_pct": bundle.negative_share_pct,
            "top_sources": bundle.top_sources,
            "top_pain_category": bundle.top_pain_category,
            "suggested_opportunity": payload.get("suggested_opportunity") or self._default_opportunity(bundle),
            "segment_notes": payload.get("segment_notes"),
            "model_used": self.model,
        }
        try:
            return InsightCard.model_validate(data)
        except ValidationError as exc:
            logger.warning("[generator] LLM schema validation failed: {e}", e=str(exc).splitlines()[0])
            return self._rule_based_card(bundle, insight_id, priority_score)

    def _rule_based_card(
        self,
        bundle: TopicBundle,
        insight_id: str,
        priority_score: float,
    ) -> InsightCard:
        return InsightCard(
            insight_id=insight_id,
            topic_id=bundle.topic_id,
            title=bundle.label,
            theme=pain_to_theme(bundle.top_pain_category),
            narrative=self._default_narrative(bundle),
            severity=default_severity(bundle),
            trend=bundle.trend,
            priority_score=priority_score,
            affected_segments=self._top_segments(bundle),
            top_unmet_needs=bundle.unmet_needs[:5],
            evidence_quotes=bundle.evidence_quotes,
            evidence_review_ids=bundle.evidence_review_ids,
            supporting_review_count=bundle.size,
            discovery_share_pct=bundle.discovery_share_pct,
            negative_share_pct=bundle.negative_share_pct,
            top_sources=bundle.top_sources,
            top_pain_category=bundle.top_pain_category,
            suggested_opportunity=self._default_opportunity(bundle),
            segment_notes=self._default_segment_notes(bundle),
            model_used="rule-based",
        )

    @staticmethod
    def _top_segments(bundle: TopicBundle, k: int = 4) -> List[str]:
        items = sorted(bundle.segment_breakdown.items(), key=lambda x: -x[1])
        segs = [s for s, _ in items if s and s != "unknown"][:k]
        if not segs and items:
            segs = [items[0][0]]
        return segs

    @staticmethod
    def _default_narrative(bundle: TopicBundle) -> str:
        quote = bundle.evidence_quotes[0] if bundle.evidence_quotes else ""
        need = bundle.unmet_needs[0] if bundle.unmet_needs else "none identified"
        return (
            f"{bundle.size} users discuss '{bundle.label}'. "
            f"{bundle.negative_share_pct:.0f}% express negative sentiment. "
            f"Top unmet need: {need}. "
            f'Example: "{quote[:200]}"'
        ).strip()

    @staticmethod
    def _default_opportunity(bundle: TopicBundle) -> str:
        if bundle.unmet_needs:
            return f"Address: {bundle.unmet_needs[0]}"
        if bundle.discovery_share_pct >= 50:
            return "Improve personalized discovery and recommendation controls for this use case."
        return f"Investigate and resolve pain around {bundle.label.lower()}."

    @staticmethod
    def _default_segment_notes(bundle: TopicBundle) -> Optional[str]:
        if len(bundle.segment_breakdown) <= 1:
            return None
        top = sorted(bundle.segment_breakdown.items(), key=lambda x: -x[1])[:3]
        parts = [f"{seg} ({cnt})" for seg, cnt in top]
        return "Most vocal segments: " + ", ".join(parts)
