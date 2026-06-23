"""Phase 3 orchestrator.

Steps:
  1. Load Phase-2 insights (dedup, optional discovery-only filter)
  2. Embed `text_to_embed` with Sentence-Transformers (cached)
  3. Cluster with BERTopic (UMAP + HDBSCAN + c-TF-IDF)
  4. For each cluster:
       - compute keywords, distribution stats, top quotes
       - generate a human-readable label (Groq if enabled, else keywords)
  5. Persist:
       - topics.csv
       - insights_with_topics.csv
       - serialized BERTopic model (data/processed/topic_model/)
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import List, Optional

import pandas as pd
from loguru import logger

from .clusterer import Clusterer
from .config import settings
from .embedder import Embedder
from .labeler import TopicLabeler, heuristic_label
from .loader import load_insights
from .schemas import Topic, TopicAssignment
from .storage import TopicStore
from .utils import setup_logging


_NOISE_LABEL = "Noise / Unclustered"


@dataclass
class ClusteringSummary:
    started_at: str
    finished_at: str
    duration_seconds: float
    insights_considered: int
    insights_clustered: int
    insights_noise: int
    n_topics: int
    embedding_model: str
    embedding_cache_hit: bool
    cluster_discovery_only: bool
    topics_csv: str
    insights_with_topics_csv: str
    embeddings_npy: str


def _mode(values: List[str], default: str = "unknown") -> str:
    vals = [v for v in values if v]
    if not vals:
        return default
    return Counter(vals).most_common(1)[0][0]


def _ranked(values: List[str], k: int = 3) -> List[str]:
    vals = [v for v in values if v]
    return [v for v, _ in Counter(vals).most_common(k)]


class ClusteringPipeline:
    """One end-to-end Phase-3 run."""

    def __init__(
        self,
        embedder: Optional[Embedder] = None,
        clusterer: Optional[Clusterer] = None,
        labeler: Optional[TopicLabeler] = None,
        store: Optional[TopicStore] = None,
        discovery_only: Optional[bool] = None,
        use_llm_labels: Optional[bool] = None,
        force_rebuild_embeddings: bool = False,
    ) -> None:
        setup_logging()
        self.embedder = embedder or Embedder()
        self.clusterer = clusterer or Clusterer()
        self.labeler = labeler or TopicLabeler(use_llm=use_llm_labels)
        self.store = store or TopicStore()
        self.discovery_only = discovery_only
        self.force_rebuild_embeddings = force_rebuild_embeddings

    def run(self) -> ClusteringSummary:
        started = datetime.now(timezone.utc)

        df = load_insights(discovery_only=self.discovery_only)
        if df.empty:
            raise RuntimeError(
                "No insights to cluster. Run Phase 2 first, or relax discovery_only."
            )

        review_ids = df["review_id"].tolist()
        docs = df["text_to_embed"].tolist()

        embeddings, was_cached = self.embedder.encode_or_load(
            texts=docs,
            review_ids=review_ids,
            force_rebuild=self.force_rebuild_embeddings,
        )

        topic_ids, probs = self.clusterer.fit(docs, embeddings)
        df = df.copy()
        df["topic_id"] = topic_ids
        df["topic_probability"] = probs

        topics = self._build_topics(df)

        topic_label_by_id = {t.topic_id: t.label for t in topics}
        assignments: List[TopicAssignment] = []
        for rid, tid, prob in zip(review_ids, topic_ids, probs):
            assignments.append(
                TopicAssignment(
                    review_id=rid,
                    topic_id=int(tid),
                    topic_label=topic_label_by_id.get(int(tid), _NOISE_LABEL),
                    topic_probability=prob,
                )
            )

        self.store.write_topics(topics)
        self.store.write_insights_with_topics(df, assignments)
        self.clusterer.save()

        finished = datetime.now(timezone.utc)

        n_noise = int((df["topic_id"] == -1).sum())
        summary = ClusteringSummary(
            started_at=started.isoformat(),
            finished_at=finished.isoformat(),
            duration_seconds=(finished - started).total_seconds(),
            insights_considered=len(df),
            insights_clustered=int((df["topic_id"] != -1).sum()),
            insights_noise=n_noise,
            n_topics=sum(1 for t in topics if t.topic_id != -1),
            embedding_model=self.embedder.model_name,
            embedding_cache_hit=was_cached,
            cluster_discovery_only=bool(
                self.discovery_only if self.discovery_only is not None
                else settings.cluster_discovery_only
            ),
            topics_csv=str(self.store.topics_path),
            insights_with_topics_csv=str(self.store.insights_with_topics_path),
            embeddings_npy=str(settings.embeddings_npy_path),
        )
        logger.info(
            "[pipeline] done in {d:.1f}s | topics={t} | clustered={c} | noise={n}",
            d=summary.duration_seconds,
            t=summary.n_topics,
            c=summary.insights_clustered,
            n=summary.insights_noise,
        )
        return summary

    def _build_topics(self, df: pd.DataFrame) -> List[Topic]:
        topics: List[Topic] = []
        total_clustered = int((df["topic_id"] != -1).sum()) or 1

        topic_info = self.clusterer.topic_info_dataframe()
        ordered_ids = topic_info["Topic"].tolist()

        for tid in ordered_ids:
            tid = int(tid)
            sub = df[df["topic_id"] == tid]
            if sub.empty:
                continue

            keywords = self.clusterer.topic_keywords(tid)

            rep_docs = self.clusterer.representative_docs(tid)
            quotes: List[str] = []
            rep_ids: List[str] = []

            if rep_docs:
                doc_to_rid = dict(zip(sub["text_to_embed"], sub["review_id"]))
                doc_to_quote = dict(zip(sub["text_to_embed"], sub["verbatim_quote"]))
                for doc in rep_docs[: settings.top_docs_per_topic]:
                    rid = doc_to_rid.get(doc)
                    if rid:
                        rep_ids.append(rid)
                        quotes.append(doc_to_quote.get(doc, doc))

            if len(quotes) < settings.top_docs_per_topic:
                pad = sub.head(settings.top_docs_per_topic).reset_index(drop=True)
                for _, row in pad.iterrows():
                    rid = str(row["review_id"])
                    if rid in rep_ids:
                        continue
                    rep_ids.append(rid)
                    quotes.append(str(row["verbatim_quote"]) or str(row["text_to_embed"]))
                    if len(quotes) >= settings.top_docs_per_topic:
                        break

            if tid == -1:
                label = _NOISE_LABEL
            else:
                label = self.labeler.label(keywords, quotes) or heuristic_label(keywords)

            top_pain = _mode(sub["pain_category"].tolist(), default="none")
            top_sent = _mode(sub["sentiment"].tolist(), default="neutral")
            top_seg = _mode(sub["segment"].tolist(), default="unknown")
            top_sources = _ranked(sub["source"].tolist(), k=3)

            discovery_share = (
                100.0 * float(sub["discovery_related"].sum()) / max(1, len(sub))
            )
            share = 100.0 * len(sub) / total_clustered if tid != -1 else 0.0

            topics.append(
                Topic(
                    topic_id=tid,
                    label=label,
                    keywords=keywords,
                    size=len(sub),
                    share_pct=round(share, 2),
                    discovery_share_pct=round(discovery_share, 2),
                    top_pain_category=top_pain,
                    top_sentiment=top_sent,
                    top_segment=top_seg,
                    top_sources=top_sources,
                    representative_quotes=quotes,
                    representative_review_ids=rep_ids,
                    embedding_model=self.embedder.model_name,
                )
            )

        topics.sort(key=lambda t: (t.topic_id == -1, -t.size))
        return topics

    @staticmethod
    def summary_to_dict(summary: ClusteringSummary) -> dict:
        return asdict(summary)
