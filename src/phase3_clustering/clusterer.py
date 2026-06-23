"""BERTopic wrapper.

We bring our own embeddings (computed once in `embedder.py`) and hand them to
BERTopic with explicit UMAP + HDBSCAN configs so the run is fully
deterministic for a given input. c-TF-IDF then surfaces representative
keywords per cluster, and BERTopic's `get_representative_docs` gives us
example reviews for the evidence panel.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from loguru import logger

from .config import settings


class Clusterer:
    """Run BERTopic over precomputed embeddings."""

    def __init__(
        self,
        min_cluster_size: Optional[int] = None,
        n_components: Optional[int] = None,
        n_neighbors: Optional[int] = None,
        random_state: int = 42,
    ) -> None:
        self.min_cluster_size = min_cluster_size or settings.min_cluster_size
        self.n_components = n_components or settings.umap_n_components
        self.n_neighbors = n_neighbors or settings.umap_n_neighbors
        self.random_state = random_state
        self._model = None

    def _build_model(self):
        from bertopic import BERTopic
        from hdbscan import HDBSCAN
        from sklearn.feature_extraction.text import CountVectorizer
        from umap import UMAP

        umap_model = UMAP(
            n_neighbors=self.n_neighbors,
            n_components=self.n_components,
            min_dist=0.0,
            metric="cosine",
            random_state=self.random_state,
        )
        hdbscan_model = HDBSCAN(
            min_cluster_size=self.min_cluster_size,
            metric="euclidean",
            cluster_selection_method="eom",
            prediction_data=True,
        )
        # "spotify" appears in nearly every review and would otherwise dominate
        # every cluster's top keywords. Drop it (and a few near-stopwords).
        domain_stopwords = ["spotify", "app", "music", "song", "songs", "user", "people", "thing", "things"]
        try:
            from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
            stop_words = list(ENGLISH_STOP_WORDS.union(domain_stopwords))
        except ImportError:
            stop_words = "english"

        vectorizer_model = CountVectorizer(
            stop_words=stop_words,
            ngram_range=(1, 2),
            min_df=2,
            max_df=0.85,
        )

        return BERTopic(
            umap_model=umap_model,
            hdbscan_model=hdbscan_model,
            vectorizer_model=vectorizer_model,
            top_n_words=10,
            calculate_probabilities=False,
            verbose=False,
        )

    def fit(
        self,
        documents: List[str],
        embeddings: np.ndarray,
    ) -> Tuple[List[int], List[Optional[float]]]:
        """Fit BERTopic; return per-doc (topic_id, probability) lists."""
        logger.info(
            "[clusterer] fitting BERTopic (docs={n}, min_cluster_size={mcs}, "
            "umap_n={un}, umap_neighbors={unb})",
            n=len(documents),
            mcs=self.min_cluster_size,
            un=self.n_components,
            unb=self.n_neighbors,
        )

        self._model = self._build_model()
        topics, probs = self._model.fit_transform(documents, embeddings=embeddings)

        if probs is None:
            prob_list: List[Optional[float]] = [None] * len(topics)
        else:
            prob_list = [float(p) if p is not None else None for p in probs]

        info = self._model.get_topic_info()
        n_topics = int((info["Topic"] >= 0).sum())
        n_noise = int(info.loc[info["Topic"] == -1, "Count"].sum()) if (-1 in info["Topic"].values) else 0
        logger.info(
            "[clusterer] done. topics={t} (excluding noise), noise_docs={nz}/{tot}",
            t=n_topics, nz=n_noise, tot=len(documents),
        )
        return [int(t) for t in topics], prob_list

    @property
    def model(self):
        if self._model is None:
            raise RuntimeError("Clusterer.fit() has not been called yet")
        return self._model

    def topic_keywords(self, topic_id: int) -> List[str]:
        """Top c-TF-IDF keywords for a given topic id."""
        words = self.model.get_topic(topic_id) or []
        return [w for w, _ in words]

    def topic_info_dataframe(self):
        """Return BERTopic's per-topic summary table."""
        return self.model.get_topic_info()

    def representative_docs(self, topic_id: int) -> List[str]:
        """Representative documents BERTopic picked for this topic (best-effort)."""
        try:
            return list(self.model.get_representative_docs(topic_id) or [])
        except Exception as exc:
            logger.debug("[clusterer] get_representative_docs({t}) failed: {e}", t=topic_id, e=exc)
            return []

    def save(self, dirpath: Optional[Path] = None) -> Path:
        """Serialize the BERTopic model (safetensors format, no pickled embeddings)."""
        target = Path(dirpath) if dirpath else settings.topic_model_path
        target.mkdir(parents=True, exist_ok=True)
        try:
            self.model.save(
                str(target),
                serialization="safetensors",
                save_ctfidf=True,
                save_embedding_model=False,
            )
            logger.info("[clusterer] saved BERTopic model -> {p}", p=target)
        except Exception as exc:
            logger.warning("[clusterer] could not save model ({e}); continuing", e=exc)
        return target
