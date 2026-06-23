"""Shared logging helpers for Phase 5."""

from __future__ import annotations

import sys

from loguru import logger

from .config import settings

_LOGGING_INITIALIZED = False


def setup_logging() -> None:
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
        settings.log_dir / "phase5_storage.log",
        level="DEBUG",
        rotation="10 MB",
        retention="14 days",
        encoding="utf-8",
    )
    _LOGGING_INITIALIZED = True
