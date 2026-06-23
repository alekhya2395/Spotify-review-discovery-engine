"""Phase 3 — Topic Modeling & Clustering.

Reads Phase 2 insights, embeds them with Sentence-Transformers, clusters with
BERTopic (UMAP + HDBSCAN + c-TF-IDF), and (optionally) asks Groq to generate
human-friendly labels for each cluster.

Outputs:
  - data/processed/embeddings.npy
  - data/processed/embedding_index.csv     (row -> review_id)
  - data/processed/topics.csv              (one row per cluster)
  - data/processed/insights_with_topics.csv (insights + topic_id + topic_label)
  - data/processed/topic_model/            (serialized BERTopic model)
"""

from .pipeline import ClusteringPipeline, ClusteringSummary
from .schemas import Topic

__all__ = ["ClusteringPipeline", "ClusteringSummary", "Topic"]
