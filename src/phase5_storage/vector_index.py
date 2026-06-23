"""Chroma vector index for semantic search over review embeddings."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from loguru import logger

from .config import settings


def _chroma_metadata(row: pd.Series) -> Dict[str, Any]:
    """Chroma accepts only scalar metadata values."""
    meta: Dict[str, Any] = {}
    for key in (
        "review_id",
        "source",
        "sentiment",
        "segment",
        "pain_category",
        "topic_id",
        "topic_label",
        "discovery_related",
    ):
        if key not in row.index:
            continue
        val = row[key]
        if pd.isna(val):
            continue
        if key == "discovery_related":
            meta[key] = bool(val) if not isinstance(val, str) else val.lower() in {"true", "1", "yes"}
        elif key == "topic_id":
            meta[key] = int(val)
        else:
            meta[key] = str(val)
    return meta


class VectorIndex:
    """Persistent Chroma collection backed by Phase-3 embeddings."""

    def __init__(
        self,
        persist_dir: Optional[Path] = None,
        collection_name: Optional[str] = None,
    ) -> None:
        self.persist_dir = Path(persist_dir) if persist_dir else settings.chroma_path
        self.collection_name = collection_name or settings.chroma_collection
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = None
        self._collection = None

    def _ensure_client(self):
        if self._client is None:
            try:
                import chromadb
            except ImportError as exc:
                raise RuntimeError(
                    "chromadb not installed. Run `pip install chromadb`."
                ) from exc
            self._client = chromadb.PersistentClient(path=str(self.persist_dir))
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def rebuild(
        self,
        embeddings: np.ndarray,
        index_df: pd.DataFrame,
        documents_df: pd.DataFrame,
        batch_size: int = 500,
    ) -> int:
        """Replace the collection contents with fresh embeddings + metadata."""
        collection = self._ensure_client()

        # Wipe and recreate for a clean rebuild
        try:
            self._client.delete_collection(self.collection_name)
        except Exception:
            pass
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        collection = self._collection

        doc_map = documents_df.set_index("review_id")
        ids = index_df["review_id"].astype(str).tolist()
        total = 0

        for start in range(0, len(ids), batch_size):
            batch_ids = ids[start : start + batch_size]
            batch_emb = embeddings[start : start + batch_size].tolist()
            docs = []
            metas = []
            for rid in batch_ids:
                if rid in doc_map.index:
                    row = doc_map.loc[rid]
                    quote = str(row.get("verbatim_quote") or row.get("text") or "")
                    docs.append(quote[:2000])
                    metas.append(_chroma_metadata(row))
                else:
                    docs.append("")
                    metas.append({"review_id": rid})

            collection.add(
                ids=batch_ids,
                embeddings=batch_emb,
                documents=docs,
                metadatas=metas,
            )
            total += len(batch_ids)

        logger.info(
            "[vector] indexed {n} vectors in Chroma ({p})",
            n=total,
            p=self.persist_dir,
        )
        return total

    def search(
        self,
        query_embedding: List[float],
        k: int = 10,
        where: Optional[Dict] = None,
    ) -> List[Dict]:
        """Return top-k semantically similar reviews."""
        collection = self._ensure_client()
        kwargs: Dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": k,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where

        result = collection.query(**kwargs)
        out = []
        if not result["ids"] or not result["ids"][0]:
            return out

        for i, rid in enumerate(result["ids"][0]):
            out.append(
                {
                    "review_id": rid,
                    "document": (result["documents"][0][i] if result.get("documents") else ""),
                    "metadata": (result["metadatas"][0][i] if result.get("metadatas") else {}),
                    "distance": (result["distances"][0][i] if result.get("distances") else None),
                    "similarity": (
                        1.0 - result["distances"][0][i]
                        if result.get("distances")
                        else None
                    ),
                }
            )
        return out

    @property
    def count(self) -> int:
        collection = self._ensure_client()
        return collection.count()
