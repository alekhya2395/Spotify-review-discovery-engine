"""Theme cluster + segment breakdown endpoints."""

from fastapi import APIRouter

from data_loader import load_themes

router = APIRouter()


@router.get("/themes")
def get_themes() -> dict:
    data = load_themes()
    themes_list = data.get("themes", {}).get("themes", []) if data else []
    return {
        "themes": themes_list,
        "segment_breakdown": data.get("segment_breakdown", {}),
    }
