"""Phase 1 — Data Collection (Ingestion Layer).

Collects raw user feedback from multiple public platforms and persists it
into the raw data lake in a unified, source-tagged schema.
"""

from .schemas import RawReview, SourceType
from .pipeline import CollectionPipeline

__all__ = ["RawReview", "SourceType", "CollectionPipeline"]
