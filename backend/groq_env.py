"""Resolve Groq API key from process env or trusted proxy header."""

from __future__ import annotations

import os

from fastapi import Request

GROQ_HEADER = "x-groq-api-key"


def groq_api_key(request: Request | None = None) -> str:
    """Return Groq key from GROQ_API_KEY env, else X-Groq-Api-Key request header."""
    env_key = os.getenv("GROQ_API_KEY", "").strip()
    if env_key:
        return env_key
    if request is not None:
        header_key = (request.headers.get(GROQ_HEADER) or "").strip()
        if header_key:
            return header_key
    return ""


def groq_chat_model() -> str:
    return os.getenv("GROQ_CHAT_MODEL", "llama-3.1-8b-instant")
