"""Lightweight RAG chatbot — semantic search + Groq synthesis."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from loguru import logger

from .config import settings
from .data import DashboardData


SYSTEM_PROMPT = """You are a product analytics assistant for Spotify PMs.
Answer questions using ONLY the provided review excerpts and insight context.
Be concise (3-6 sentences). Cite specific user pain when relevant.
If the context is insufficient, say what is missing — do not invent data."""


def _format_context(hits: List[Dict[str, Any]], cards: Optional[List[Dict[str, Any]]] = None) -> str:
    parts = []
    if cards:
        parts.append("=== INSIGHT CARDS ===")
        for c in cards[:3]:
            parts.append(
                f"- {c.get('insight_id')}: {c.get('title')} "
                f"(priority={c.get('priority_score')}, severity={c.get('severity')})"
            )
            parts.append(f"  {c.get('narrative', '')[:400]}")

    parts.append("\n=== REVIEW EXCERPTS ===")
    for i, hit in enumerate(hits, start=1):
        detail = hit.get("detail") or hit.get("metadata") or {}
        quote = detail.get("verbatim_quote") or hit.get("document") or ""
        topic = detail.get("topic_label", "")
        source = detail.get("source", "")
        sim = hit.get("similarity")
        sim_s = f"{sim:.2f}" if sim is not None else "?"
        parts.append(f'{i}. [{source}] topic="{topic}" sim={sim_s}: "{quote[:350]}"')
    return "\n".join(parts)


class ReviewChatbot:
    """Ask-the-reviews RAG helper backed by Phase-5 semantic search."""

    def __init__(self, data: DashboardData) -> None:
        self.data = data

    def ask(self, question: str) -> Dict[str, Any]:
        hits = self.data.search(question, k=settings.chat_context_k)
        related_cards = self.data.all_cards(limit=5)
        # Surface cards whose title/theme loosely match the question
        q = question.lower()
        matched_cards = [
            self.data.card(str(r["insight_id"]))
            for _, r in related_cards.iterrows()
            if q in str(r["title"]).lower() or q in str(r["theme"]).lower()
        ]
        matched_cards = [c for c in matched_cards if c][:3]

        context = _format_context(hits, matched_cards)

        if not settings.groq_api_key:
            return {
                "answer": (
                    "GROQ_API_KEY is not set. Showing retrieved reviews only — "
                    "add a key to enable LLM synthesis."
                ),
                "hits": hits,
                "context": context,
                "model_used": None,
            }

        try:
            from groq import Groq

            client = Groq(api_key=settings.groq_api_key, timeout=60)
            resp = client.chat.completions.create(
                model=settings.groq_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"Question: {question}\n\nContext:\n{context}",
                    },
                ],
                temperature=0.2,
                max_tokens=800,
            )
            answer = (resp.choices[0].message.content or "").strip()
            model_used = settings.groq_model
        except Exception as exc:
            logger.warning("[chat] completion failed: {e}", e=exc)
            answer = f"LLM call failed ({exc}). Retrieved {len(hits)} relevant reviews below."
            model_used = None

        return {
            "answer": answer,
            "hits": hits,
            "context": context,
            "model_used": model_used,
        }
