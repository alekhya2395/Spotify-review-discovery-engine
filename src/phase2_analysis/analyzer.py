"""Batch reviews → Groq → validated `Insight` objects.

Responsibilities:
- Chunk an input list of reviews into batches of `batch_size`
- Render the LLM prompt for each batch
- Parse the JSON response and validate each item against `Insight`
- Tolerate per-item failures (skip them, keep going)
- Emit each batch's insights via an optional callback so callers can persist
  per-batch progress (vital when the LLM hits rate limits mid-run).
"""

from __future__ import annotations

import json
from typing import Callable, Dict, List, Optional

from loguru import logger
from pydantic import ValidationError

from .config import settings
from .groq_client import GroqClient
from .prompts import SYSTEM_PROMPT, build_user_prompt
from .schemas import Insight


OnBatchCallback = Callable[[List[Insight]], None]


def chunked(items: List[Dict], size: int):
    """Yield successive chunks of `size` from `items`."""
    for i in range(0, len(items), size):
        yield items[i : i + size]


class Analyzer:
    """Run a list of reviews through Groq and return validated insights."""

    def __init__(
        self,
        client: Optional[GroqClient] = None,
        batch_size: Optional[int] = None,
    ) -> None:
        self.client = client or GroqClient()
        self.batch_size = batch_size or settings.groq_batch_size

    def analyze(
        self,
        reviews: List[Dict],
        on_batch: Optional[OnBatchCallback] = None,
        stop_on_consecutive_failures: int = 3,
    ) -> List[Insight]:
        """Process all reviews in batches.

        Parameters
        ----------
        reviews:
            List of review dicts (`review_id`, `source`, `text`, ...)
        on_batch:
            Optional callback invoked with each successful batch's insights.
            Use this to persist progress incrementally (e.g. append to CSV)
            so a mid-run rate-limit doesn't lose work.
        stop_on_consecutive_failures:
            After this many consecutive batch failures (e.g. rate-limit
            exhaustion), abort the run cleanly so the caller can resume later.
        """
        all_insights: List[Insight] = []
        if not reviews:
            return all_insights

        batches = list(chunked(reviews, self.batch_size))
        logger.info(
            "[analyzer] {n} reviews -> {b} batches of {s}",
            n=len(reviews),
            b=len(batches),
            s=self.batch_size,
        )

        consecutive_failures = 0
        for idx, batch in enumerate(batches, start=1):
            try:
                insights = self._analyze_batch(batch)
            except Exception as exc:
                consecutive_failures += 1
                logger.error(
                    "[analyzer] batch {i}/{n} failed ({cf} in a row): {e}",
                    i=idx, n=len(batches), cf=consecutive_failures, e=exc,
                )
                if consecutive_failures >= stop_on_consecutive_failures:
                    logger.warning(
                        "[analyzer] aborting after {cf} consecutive failures "
                        "(likely rate-limited). {done}/{total} batches done. "
                        "Re-run later — dedup will skip what's already saved.",
                        cf=consecutive_failures,
                        done=idx - 1,
                        total=len(batches),
                    )
                    break
                continue

            consecutive_failures = 0
            all_insights.extend(insights)
            if on_batch is not None and insights:
                try:
                    on_batch(insights)
                except Exception as cb_exc:
                    logger.error("[analyzer] on_batch callback raised: {e}", e=cb_exc)

            logger.info(
                "[analyzer] batch {i}/{n} -> +{a} insights (total={t})",
                i=idx,
                n=len(batches),
                a=len(insights),
                t=len(all_insights),
            )

        return all_insights

    def _analyze_batch(self, batch: List[Dict]) -> List[Insight]:
        user_prompt = build_user_prompt(batch)
        raw = self.client.chat_json(SYSTEM_PROMPT, user_prompt)

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning("[analyzer] malformed JSON from LLM (len={l}): {e}", l=len(raw), e=exc)
            return []

        items = payload.get("insights")
        if not isinstance(items, list):
            logger.warning("[analyzer] missing or non-list 'insights' key in LLM response")
            return []

        out: List[Insight] = []
        by_id = {r["review_id"]: r for r in batch}

        for item in items:
            if not isinstance(item, dict):
                continue

            review_id = (item.get("review_id") or "").strip()
            origin = by_id.get(review_id)
            if origin is None:
                logger.debug("[analyzer] LLM returned unknown review_id={r}", r=review_id)
                continue

            item["source"] = origin.get("source") or item.get("source") or "unknown"
            item["model_used"] = self.client.model

            try:
                out.append(Insight.model_validate(item))
            except ValidationError as exc:
                logger.warning(
                    "[analyzer] schema validation failed for review_id={r}: {e}",
                    r=review_id,
                    e=str(exc).splitlines()[0],
                )

        return out
