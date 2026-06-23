"""Sentence-Transformers wrapper with on-disk caching.

Embedding 2k+ docs from cold cache takes ~30-60 s on CPU; cached re-runs are
instant. The cache is keyed by (model_id, list_of_review_ids) — any change
invalidates it. Cache lives under `data/processed/embeddings.npy` +
`embedding_index.csv` so it's inspectable / re-usable by Phase 4.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
from loguru import logger

from .config import settings


# Stop sentence-transformers from spawning a HF Hub download progress bar on every run.
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")


class Embedder:
    """Lazy-loaded Sentence-Transformers wrapper."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        batch_size: Optional[int] = None,
    ) -> None:
        self.model_name = model_name or settings.embed_model
        self.batch_size = batch_size or settings.embed_batch_size
        self._model = None

    def _ensure_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RuntimeError(
                    "sentence-transformers not installed. "
                    "Run `pip install sentence-transformers`."
                ) from exc
            logger.info("[embedder] loading {m} (first call only)...", m=self.model_name)
            self._model = SentenceTransformer(self.model_name)
            logger.info(
                "[embedder] model loaded (dim={d})",
                d=self._model.get_sentence_embedding_dimension(),
            )
        return self._model

    def encode(self, texts: List[str]) -> np.ndarray:
        """Encode texts to normalized dense vectors."""
        model = self._ensure_model()
        emb = model.encode(
            texts,
            batch_size=self.batch_size,
            show_progress_bar=True,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return emb.astype(np.float32, copy=False)

    def encode_or_load(
        self,
        texts: List[str],
        review_ids: List[str],
        npy_path: Optional[Path] = None,
        index_csv_path: Optional[Path] = None,
        force_rebuild: bool = False,
    ) -> Tuple[np.ndarray, bool]:
        """Return (embeddings, was_cached).

        Cache is reused only when the saved review_id ordering exactly matches
        the request. Any insertion / reorder / new model invalidates it.
        """
        npy = Path(npy_path) if npy_path else settings.embeddings_npy_path
        idx_csv = Path(index_csv_path) if index_csv_path else settings.embedding_index_csv_path
        npy.parent.mkdir(parents=True, exist_ok=True)

        if not force_rebuild and npy.exists() and idx_csv.exists():
            try:
                idx_df = pd.read_csv(idx_csv)
                cached_ids = idx_df["review_id"].astype(str).tolist()
                cached_model = idx_df["embed_model"].iloc[0] if "embed_model" in idx_df.columns else ""
                if cached_ids == review_ids and cached_model == self.model_name:
                    emb = np.load(npy)
                    if emb.shape[0] == len(review_ids):
                        logger.info(
                            "[embedder] cache HIT ({n} vectors, model={m})",
                            n=emb.shape[0], m=self.model_name,
                        )
                        return emb, True
                logger.info("[embedder] cache MISS — recomputing")
            except Exception as exc:
                logger.warning("[embedder] could not read cache ({e}) — recomputing", e=exc)

        emb = self.encode(texts)
        np.save(npy, emb)
        pd.DataFrame(
            {
                "row": list(range(len(review_ids))),
                "review_id": review_ids,
                "embed_model": [self.model_name] * len(review_ids),
            }
        ).to_csv(idx_csv, index=False)
        logger.info(
            "[embedder] wrote embeddings={n} ({d} dims) -> {p}",
            n=emb.shape[0], d=emb.shape[1], p=npy,
        )
        return emb, False
