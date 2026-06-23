"""Shared utilities: logging setup and resilient retry helpers (mirrors Phase 1)."""

from __future__ import annotations

import sys
from typing import Callable, Type

from loguru import logger
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .config import settings

_LOGGING_INITIALIZED = False


def setup_logging() -> None:
    """Configure loguru once per process."""
    global _LOGGING_INITIALIZED
    if _LOGGING_INITIALIZED:
        return

    settings.ensure_directories()
    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.log_level.upper(),
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{line}</cyan> | {message}"
        ),
    )
    logger.add(
        settings.log_dir / "phase2_analysis.log",
        level="DEBUG",
        rotation="10 MB",
        retention="14 days",
        encoding="utf-8",
    )
    _LOGGING_INITIALIZED = True


def with_retries(*exception_types: Type[BaseException]) -> Callable:
    """Decorator factory for exponential-backoff retries on transient errors."""
    if not exception_types:
        exception_types = (Exception,)

    return retry(
        reraise=True,
        stop=stop_after_attempt(settings.retry_max_attempts),
        wait=wait_exponential(
            multiplier=settings.retry_backoff_seconds,
            min=settings.retry_backoff_seconds,
            max=settings.retry_backoff_seconds * 8,
        ),
        retry=retry_if_exception_type(exception_types),
    )
