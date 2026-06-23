"""Centralized configuration for Phase 3 (clustering & topic modeling).

Loads embedding model, BERTopic hyperparameters, and I/O paths from the
environment / `.env`. Mirrors the Phase 2 settings pattern.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the clustering pipeline."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    embed_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")
    embed_batch_size: int = Field(default=64, ge=1, le=512)

    min_cluster_size: int = Field(default=8, ge=2)
    umap_n_components: int = Field(default=5, ge=2, le=64)
    umap_n_neighbors: int = Field(default=10, ge=2)
    top_docs_per_topic: int = Field(default=5, ge=1, le=50)

    cluster_discovery_only: bool = Field(default=False)
    llm_topic_labels: bool = Field(default=True)

    groq_api_key: Optional[str] = None
    groq_model: str = Field(default="llama-3.3-70b-versatile")
    groq_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    groq_max_tokens: int = Field(default=400, ge=64, le=4000)

    processed_data_dir: Path = Field(default=Path("./data/processed"))
    insights_csv: str = Field(default="insights.csv")
    topics_csv: str = Field(default="topics.csv")
    insights_with_topics_csv: str = Field(default="insights_with_topics.csv")
    embeddings_npy: str = Field(default="embeddings.npy")
    embedding_index_csv: str = Field(default="embedding_index.csv")
    topic_model_dir: str = Field(default="topic_model")

    request_timeout_seconds: int = Field(default=60, ge=5)
    retry_max_attempts: int = Field(default=4, ge=1)
    retry_backoff_seconds: float = Field(default=2.0, ge=0)

    log_level: str = Field(default="INFO")
    log_dir: Path = Field(default=Path("./logs"))

    @field_validator("processed_data_dir", "log_dir", mode="before")
    @classmethod
    def _coerce_path(cls, v):
        return Path(v) if not isinstance(v, Path) else v

    @property
    def insights_csv_path(self) -> Path:
        return self.processed_data_dir / self.insights_csv

    @property
    def topics_csv_path(self) -> Path:
        return self.processed_data_dir / self.topics_csv

    @property
    def insights_with_topics_csv_path(self) -> Path:
        return self.processed_data_dir / self.insights_with_topics_csv

    @property
    def embeddings_npy_path(self) -> Path:
        return self.processed_data_dir / self.embeddings_npy

    @property
    def embedding_index_csv_path(self) -> Path:
        return self.processed_data_dir / self.embedding_index_csv

    @property
    def topic_model_path(self) -> Path:
        return self.processed_data_dir / self.topic_model_dir

    def ensure_directories(self) -> None:
        self.processed_data_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def groq_enabled(self) -> bool:
        return bool(self.groq_api_key)


settings = Settings()
