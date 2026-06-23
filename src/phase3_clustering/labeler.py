"""Topic labeling.

Two strategies:

1. **Heuristic (always available):** join the top-3 c-TF-IDF keywords. Fast,
   no API needed, but reads like a bag-of-words (e.g. "shuffle / playlist /
   queue").

2. **LLM (preferred when GROQ_API_KEY is set):** show the LLM the top keywords
   AND a few representative quotes and ask for a 3-7 word product-team-ready
   title (e.g. "Shuffle keeps replaying same handful of songs").

The labeler always returns a non-empty string; LLM failures silently fall
back to the heuristic so a missing key never aborts Phase 3.
"""

from __future__ import annotations

import json
import re
from typing import Iterable, List, Optional

from loguru import logger

from .config import settings


_TITLE_MAX_WORDS = 9


def heuristic_label(keywords: Iterable[str]) -> str:
    """Pretty-printed top-3 keywords joined with slashes."""
    words = [w.strip() for w in keywords if w and w.strip()]
    if not words:
        return "Unlabeled"
    top = words[:3]
    return " / ".join(top)


_LABEL_SYSTEM_PROMPT = """You are a senior product researcher at Spotify.
You will receive a cluster of user-feedback quotes about the Spotify app
along with the keywords that define the cluster.

Your job: produce a SHORT, neutral title (3-7 words) that a PM could paste
straight into a Jira ticket or roadmap. The title must:
- Describe the user problem or behavior — NOT just list keywords.
- Be specific (avoid generic phrases like "user feedback" or "spotify issues").
- Avoid hype, emojis, marketing language, and trailing punctuation.

Respond with strict JSON:
  {"label": "<your title>"}
""".strip()


def _build_label_user_prompt(keywords: List[str], quotes: List[str]) -> str:
    kw_str = ", ".join(keywords[:10]) if keywords else "(no keywords)"
    quote_block = "\n".join(f"- {q}" for q in quotes[:5] if q)
    if not quote_block:
        quote_block = "(no quotes available)"
    return (
        f"CLUSTER KEYWORDS:\n{kw_str}\n\n"
        f"REPRESENTATIVE QUOTES:\n{quote_block}\n\n"
        "Return only the JSON object."
    )


def _trim_label(raw: str) -> str:
    """Tidy LLM output: strip quotes, collapse whitespace, cap words."""
    s = raw.strip().strip('"').strip("'")
    s = re.sub(r"\s+", " ", s)
    s = s.rstrip(".:;,")
    words = s.split()
    if len(words) > _TITLE_MAX_WORDS:
        s = " ".join(words[:_TITLE_MAX_WORDS])
    return s


class TopicLabeler:
    """Generate human-friendly topic titles, optionally backed by an LLM.

    Failure modes (rate limits, decommissioned models, JSON-mode mismatches,
    chain-of-thought models that won't fit JSON schema) fall back IMMEDIATELY
    to the keyword heuristic — we deliberately bypass the GroqClient retry
    decorator here because labeling is a best-effort enrichment, not a
    critical path, and a 30-second retry per topic would balloon the run.
    """

    def __init__(self, use_llm: Optional[bool] = None) -> None:
        self.use_llm = settings.llm_topic_labels if use_llm is None else use_llm
        self._raw_client = None
        self._model: Optional[str] = None
        self._consecutive_failures = 0
        self._max_consecutive_failures = 5

        if self.use_llm and not settings.groq_enabled():
            logger.warning(
                "[labeler] LLM labels requested but GROQ_API_KEY is empty — "
                "falling back to heuristic labels."
            )
            self.use_llm = False

        if self.use_llm:
            try:
                from groq import Groq

                self._raw_client = Groq(
                    api_key=settings.groq_api_key,
                    timeout=settings.request_timeout_seconds,
                )
                self._model = settings.groq_model
                logger.info("[labeler] LLM labeling enabled (model={m})", m=self._model)
            except Exception as exc:
                logger.warning(
                    "[labeler] could not init Groq client ({e}); using heuristic labels", e=exc
                )
                self.use_llm = False
                self._raw_client = None

    def _call_llm(self, keywords: List[str], quotes: List[str]) -> Optional[str]:
        """Single-shot LLM call. Returns the parsed label or None on any failure."""
        assert self._raw_client is not None
        try:
            resp = self._raw_client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": _LABEL_SYSTEM_PROMPT},
                    {"role": "user", "content": _build_label_user_prompt(keywords, quotes)},
                ],
                temperature=settings.groq_temperature,
                max_tokens=settings.groq_max_tokens,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            short = str(exc).splitlines()[0][:160]
            logger.debug("[labeler] LLM call failed: {e}", e=short)
            return None

        if not resp.choices:
            return None
        content = (resp.choices[0].message.content or "").strip()
        if not content:
            return None

        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            return None

        label = _trim_label(str(payload.get("label", "")).strip())
        return label or None

    def label(self, keywords: List[str], quotes: List[str]) -> str:
        """Return a human-friendly title for one cluster."""
        fallback = heuristic_label(keywords)

        if not self.use_llm or self._raw_client is None:
            return fallback

        if self._consecutive_failures >= self._max_consecutive_failures:
            return fallback

        label = self._call_llm(keywords, quotes)
        if label:
            self._consecutive_failures = 0
            return label

        self._consecutive_failures += 1
        if self._consecutive_failures == self._max_consecutive_failures:
            logger.warning(
                "[labeler] {n} consecutive LLM failures — disabling LLM labels for the rest of this run",
                n=self._max_consecutive_failures,
            )
        return fallback
