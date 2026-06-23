"""Returns the final markdown report."""

from fastapi import APIRouter

from data_loader import load_report_md

router = APIRouter()


@router.get("/report")
def get_report() -> dict:
    return {"markdown": load_report_md()}
