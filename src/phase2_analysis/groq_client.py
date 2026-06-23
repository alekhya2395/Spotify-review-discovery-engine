"""Thin wrapper around the Groq SDK.

- Lazy-imports the SDK so the rest of the package is importable even if the
  user hasn't installed `groq` yet.
- Enforces strict JSON mode (`response_format={"type": "json_object"}`).
- Wraps every call in `tenacity` retries for transient API failures.
"""

from __future__ import annotations

from typing import Optional

from loguru import logger

from .config import settings
from .utils import with_retries


class GroqClientError(Exception):
    """Raised when the Groq client cannot be used."""


class GroqClient:
    """Minimal Groq chat-completion wrapper."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout_seconds: Optional[int] = None,
    ) -> None:
        self.api_key = api_key or settings.groq_api_key
        self.model = model or settings.groq_model
        self.temperature = settings.groq_temperature if temperature is None else temperature
        self.max_tokens = max_tokens or settings.groq_max_tokens
        self.timeout_seconds = timeout_seconds or settings.request_timeout_seconds

        if not self.api_key:
            raise GroqClientError(
                "GROQ_API_KEY is not set. Get a free key at https://console.groq.com/keys"
            )

        try:
            from groq import Groq
        except ImportError as exc:
            raise GroqClientError(
                "`groq` package not installed. Run `pip install groq` (>=0.11.0)."
            ) from exc

        self._client = Groq(api_key=self.api_key, timeout=self.timeout_seconds)
        logger.info("[groq] client ready (model={m})", m=self.model)

    @with_retries(Exception)
    def chat_json(self, system_prompt: str, user_prompt: str) -> str:
        """Send a chat completion in strict JSON mode and return the raw string.

        Retries on any exception (rate limits, transient 5xx) with exponential
        backoff per `Settings.retry_*`.
        """
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            logger.warning("[groq] chat completion failed: {e}", e=exc)
            raise

        if not resp.choices:
            raise GroqClientError("Groq returned no choices")
        content = resp.choices[0].message.content or ""
        if not content.strip():
            raise GroqClientError("Groq returned empty content")
        return content
