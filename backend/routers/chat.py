"""Claude-grounded chat over the insights dataset.

The frontend POSTs a message; we ground it on themes + a sample of insights
and call Claude with the CUSTOM_GPT_SYSTEM_PROMPT from analyzer/prompts.py.
"""

import json
import os
import sys
from pathlib import Path

from anthropic import Anthropic
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# Allow importing analyzer.prompts from the parent project tree
sys.path.append(str(Path(__file__).resolve().parents[2]))
try:
    from analyzer.prompts import CUSTOM_GPT_SYSTEM_PROMPT
except Exception:
    # Fallback inline prompt if parent tree isn't on path in deploy
    CUSTOM_GPT_SYSTEM_PROMPT = (
        "You are the Spotify Discovery Insights Agent. Ground answers in the data "
        "provided, cite verbatim quotes and theme IDs, and speak PM-fluent."
    )

from data_loader import load_insights_df, load_themes

router = APIRouter()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=2000)
    history: list[dict] | None = None  # [{"role":"user","content":"..."}]


class ChatResponse(BaseModel):
    answer: str
    grounding_size_chars: int


def _build_grounding() -> str:
    themes = load_themes()
    df = load_insights_df()
    sample = []
    if not df.empty:
        disc = df[df["is_discovery_related"] == True]  # noqa: E712
        cols = ["pain_category", "specific_pain", "geography", "listening_style", "verbatim_quote", "unmet_need"]
        cols = [c for c in cols if c in disc.columns]
        sample = disc.head(40)[cols].where(disc[cols].notna(), None).to_dict(orient="records")
    grounding = {"themes": themes, "sample_insights": sample}
    return json.dumps(grounding, ensure_ascii=False)[:30000]


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not set on backend")

    grounding = _build_grounding()
    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    messages: list[dict] = []
    if req.history:
        for m in req.history[-6:]:
            if m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str):
                messages.append({"role": m["role"], "content": m["content"]})

    messages.append({
        "role": "user",
        "content": (
            f"Use the data below to answer. Be specific, cite theme IDs (T1, T2...) "
            f"and verbatim quotes when relevant.\n\nDATA (JSON):\n{grounding}\n\n"
            f"QUESTION: {req.question}"
        ),
    })

    resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1500,
        system=CUSTOM_GPT_SYSTEM_PROMPT,
        messages=messages,
    )
    answer = resp.content[0].text
    return ChatResponse(answer=answer, grounding_size_chars=len(grounding))
