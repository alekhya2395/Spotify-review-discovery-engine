"""Phase 5 — Storage & Indexing.

Consolidates Phases 1–4 outputs into queryable stores:
  - DuckDB warehouse (reviews, insights, topics, cards)
  - Chroma vector index (semantic search over review embeddings)
  - SQLite metadata catalog (index runs, model versions)
"""

from .pipeline import IndexingPipeline, IndexingSummary
from .query import QueryEngine

__all__ = ["IndexingPipeline", "IndexingSummary", "QueryEngine"]
