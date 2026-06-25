"""Discovery insights endpoint."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter

sys.path.append(str(Path(__file__).resolve().parents[1]))

from discovery_insights import compute_discovery_insights  # noqa: E402

router = APIRouter()


@router.get("/discovery-insights")
def discovery_insights() -> dict:
    return compute_discovery_insights()
