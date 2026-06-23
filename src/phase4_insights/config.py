"""Centralized configuration for Phase 4 (insight card generation)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the insight-generation pipeline."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    processed_data_dir: Path = Field(default=Path("./data/processed"))
    raw_data_dir: Path = Field(default=Path("./data/raw"))
    topics_csv: str = Field(default="topics.csv")
    insights_with_topics_csv: str = Field(default="insights_with_topics.csv")
    insight_cards_csv: str = Field(default="insight_cards.csv")
    insight_cards_json: str = Field(default="insight_cards.json")

    min_topic_size: int = Field(default=10, ge=1, validation_alias="PHASE4_MIN_TOPIC_SIZE")
    max_evidence_quotes: int = Field(default=8, ge=1, le=20, validation_alias="PHASE4_MAX_EVIDENCE_QUOTES")
    include_noise_topic: bool = Field(default=False, validation_alias="PHASE4_INCLUDE_NOISE")
    discovery_topics_only: bool = Field(default=False, validation_alias="PHASE4_DISCOVERY_ONLY")
    min_discovery_share_pct: float = Field(
        default=50.0, ge=0.0, le=100.0, validation_alias="PHASE4_MIN_DISCOVERY_SHARE_PCT"
    )
    use_llm_cards: bool = Field(default=True, validation_alias="PHASE4_USE_LLM_CARDS")

    groq_api_key: Optional[str] = None
    groq_model: str = Field(default="llama-3.3-70b-versatile")
    groq_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    groq_max_tokens: int = Field(default=2000, ge=256, le=8000)

    request_timeout_seconds: int = Field(default=90, ge=5)
    retry_max_attempts: int = Field(default=3, ge=1)
    retry_backoff_seconds: float = Field(default=2.0, ge=0)

    log_level: str = Field(default="INFO")
    log_dir: Path = Field(default=Path("./logs"))

    @field_validator("processed_data_dir", "raw_data_dir", "log_dir", mode="before")
    @classmethod
    def _coerce_path(cls, v):
        return Path(v) if not isinstance(v, Path) else v

    @property
    def topics_csv_path(self) -> Path:
        return self.processed_data_dir / self.topics_csv

    @property
    def insights_with_topics_csv_path(self) -> Path:
        return self.processed_data_dir / self.insights_with_topics_csv

    @property
    def insight_cards_csv_path(self) -> Path:
        return self.processed_data_dir / self.insight_cards_csv

    @property
    def insight_cards_json_path(self) -> Path:
        return self.processed_data_dir / self.insight_cards_json

    def ensure_directories(self) -> None:
        self.processed_data_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def groq_enabled(self) -> bool:
        return bool(self.groq_api_key)


settings = Settings()
