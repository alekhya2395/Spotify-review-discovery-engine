"""Root-cause and user-segment endpoints."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter

sys.path.append(str(Path(__file__).resolve().parents[1]))

from root_causes import compute_root_causes  # noqa: E402
from user_segments import compute_user_segments  # noqa: E402

router = APIRouter()


@router.get("/root-causes")
def root_causes() -> dict:
    return compute_root_causes()


@router.get("/user-segments")
def user_segments() -> dict:
    return compute_user_segments()
