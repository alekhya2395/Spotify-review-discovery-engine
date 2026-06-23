"""Phase 2 — AI Analysis (Groq + Llama 3.3 70B).

Reads raw reviews collected by Phase 1, sends them to Groq in batches of N,
extracts structured insights, and appends them to a deduplicated CSV.
"""

from .schemas import Insight, PainCategory, Segment, Sentiment
from .pipeline import AnalysisPipeline

__all__ = [
    "Insight",
    "PainCategory",
    "Segment",
    "Sentiment",
    "AnalysisPipeline",
]
