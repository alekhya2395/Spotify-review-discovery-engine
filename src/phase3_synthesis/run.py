"""CLI entry point for Phase 3 synthesis.

Usage:
    python -m src.phase3_synthesis.run
"""

from __future__ import annotations

import sys
from loguru import logger

from .pipeline import run_synthesis


def main() -> None:
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")
    logger.add("logs/phase3_synthesis.log", level="DEBUG", rotation="10 MB")

    run_synthesis()


if __name__ == "__main__":
    main()
