"""FastAPI entrypoint for the Spotify Discovery Insights backend.

Run locally:
    cd backend
    uvicorn main:app --reload --port 8000

Then open:
    http://localhost:8000/docs        (interactive Swagger UI)
    http://localhost:8000/api/health  (health check)
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

_BACKEND = Path(__file__).resolve().parent
_ROOT = _BACKEND.parent
load_dotenv(_BACKEND / ".env")
load_dotenv(_ROOT / ".env", override=True)

from data_loader import data_summary  # noqa: E402
from routers import chat, insights, report, stats, themes  # noqa: E402

_DEFAULT_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv("ALLOWED_ORIGINS", _DEFAULT_ORIGINS).split(",")
    if o.strip()
]

app = FastAPI(
    title="Spotify Discovery Insights API",
    description="AI-powered review analysis backend. Built for the Next Leap PM Fellowship Graduation Project.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS if "*" not in ALLOWED_ORIGINS else ["*"],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> JSONResponse:
    return JSONResponse({
        "service": "spotify-discovery-insights",
        "status": "ok",
        "docs": "/docs",
        "health": "/api/health",
    })


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "data": data_summary()}


app.include_router(stats.router, prefix="/api", tags=["stats"])
app.include_router(insights.router, prefix="/api", tags=["insights"])
app.include_router(themes.router, prefix="/api", tags=["themes"])
app.include_router(report.router, prefix="/api", tags=["report"])
app.include_router(chat.router, prefix="/api", tags=["chat"])
