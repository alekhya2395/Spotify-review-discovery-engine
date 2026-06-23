"""Centralized configuration for Phase 2 analysis.

Loads Groq + I/O settings from environment variables (and optional .env).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the analysis pipeline."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    groq_api_key: Optional[str] = None
    groq_model: str = Field(default="llama-3.3-70b-versatile")
    groq_batch_size: int = Field(default=10, ge=1, le=50)
    groq_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    groq_max_tokens: int = Field(default=4000, ge=256, le=32000)

    raw_data_dir: Path = Field(default=Path("./data/raw"))
    processed_data_dir: Path = Field(default=Path("./data/processed"))
    insights_csv: str = Field(default="insights.csv")

    max_reviews_per_analysis_run: int = Field(default=0, ge=0)

    request_timeout_seconds: int = Field(default=60, ge=5)
    retry_max_attempts: int = Field(default=4, ge=1)
    retry_backoff_seconds: float = Field(default=2.0, ge=0)

    log_level: str = Field(default="INFO")
    log_dir: Path = Field(default=Path("./logs"))

    @field_validator("raw_data_dir", "processed_data_dir", "log_dir", mode="before")
    @classmethod
    def _coerce_path(cls, v):
        return Path(v) if not isinstance(v, Path) else v

    @property
    def insights_csv_path(self) -> Path:
        return self.processed_data_dir / self.insights_csv

    def ensure_directories(self) -> None:
        self.processed_data_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def groq_enabled(self) -> bool:
        return bool(self.groq_api_key)


settings = Settings()
