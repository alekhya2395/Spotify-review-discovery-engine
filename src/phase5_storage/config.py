"""Centralized configuration for Phase 5 (storage & indexing)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the indexing pipeline."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    processed_data_dir: Path = Field(default=Path("./data/processed"))
    raw_data_dir: Path = Field(default=Path("./data/raw"))
    index_dir: Path = Field(default=Path("./data/index"), validation_alias="INDEX_DATA_DIR")

    warehouse_db: str = Field(default="warehouse.duckdb", validation_alias="PHASE5_WAREHOUSE_DB")
    catalog_db: str = Field(default="catalog.db", validation_alias="PHASE5_CATALOG_DB")
    chroma_dir: str = Field(default="chroma", validation_alias="PHASE5_CHROMA_DIR")
    chroma_collection: str = Field(default="review_embeddings", validation_alias="PHASE5_CHROMA_COLLECTION")

    embed_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")
    default_search_k: int = Field(default=10, ge=1, le=100, validation_alias="PHASE5_DEFAULT_SEARCH_K")

    insights_csv: str = Field(default="insights.csv")
    topics_csv: str = Field(default="topics.csv")
    insights_with_topics_csv: str = Field(default="insights_with_topics.csv")
    insight_cards_csv: str = Field(default="insight_cards.csv")
    embeddings_npy: str = Field(default="embeddings.npy")
    embedding_index_csv: str = Field(default="embedding_index.csv")

    log_level: str = Field(default="INFO")
    log_dir: Path = Field(default=Path("./logs"))

    @field_validator("processed_data_dir", "raw_data_dir", "index_dir", "log_dir", mode="before")
    @classmethod
    def _coerce_path(cls, v):
        return Path(v) if not isinstance(v, Path) else v

    @property
    def warehouse_path(self) -> Path:
        return self.index_dir / self.warehouse_db

    @property
    def catalog_path(self) -> Path:
        return self.index_dir / self.catalog_db

    @property
    def chroma_path(self) -> Path:
        return self.index_dir / self.chroma_dir

    @property
    def embeddings_npy_path(self) -> Path:
        return self.processed_data_dir / self.embeddings_npy

    @property
    def embedding_index_csv_path(self) -> Path:
        return self.processed_data_dir / self.embedding_index_csv

    def ensure_directories(self) -> None:
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
