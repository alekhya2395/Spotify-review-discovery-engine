"""Phase 4 — Insight Generation (PM-ready cards).

Reads Phase 3 topic clusters + per-review insights, aggregates signals,
scores priority, and uses Groq (RAG-style) to synthesize actionable insight
cards for product managers.

Outputs:
  - data/processed/insight_cards.csv
  - data/processed/insight_cards.json
"""

from .pipeline import GenerationPipeline, GenerationSummary
from .schemas import InsightCard, Severity, Trend

__all__ = [
    "GenerationPipeline",
    "GenerationSummary",
    "InsightCard",
    "Severity",
    "Trend",
]
