"""Configuration for Phase 3 synthesis."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SynthesisSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    processed_data_dir: Path = Field(default=Path("./data/processed"))
    synthesis_output_dir: Path = Field(default=Path("./data/synthesis"))
    insights_csv: str = Field(default="insights.csv")

    min_theme_count: int = Field(default=3, description="Minimum reviews to form a theme")
    top_n_quotes: int = Field(default=5, description="Quotes per theme in the report")
    top_n_themes: int = Field(default=15, description="Max themes in the final report")

    log_level: str = Field(default="INFO")

    @property
    def insights_csv_path(self) -> Path:
        return self.processed_data_dir / self.insights_csv

    def ensure_directories(self) -> None:
        self.synthesis_output_dir.mkdir(parents=True, exist_ok=True)


settings = SynthesisSettings()
