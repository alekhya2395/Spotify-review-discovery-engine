"""Centralized configuration for Phase 1 collection.

Loads settings from environment variables (and an optional .env file).
A single `settings` object is imported by all connectors and the pipeline.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the collection pipeline."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    spotify_app_store_id: str = Field(default="324684580")
    spotify_play_store_id: str = Field(default="com.spotify.music")

    reddit_client_id: Optional[str] = None
    reddit_client_secret: Optional[str] = None
    reddit_user_agent: str = Field(default="spotify-review-engine/0.1")
    reddit_subreddits: str = Field(default="spotify,truespotify")

    community_base_url: str = Field(default="https://community.spotify.com")

    raw_data_dir: Path = Field(default=Path("./data/raw"))
    max_reviews_per_source: int = Field(default=2000, ge=1)

    app_store_countries: str = Field(default="us,gb,in")
    play_store_langs: str = Field(default="en")
    play_store_countries: str = Field(default="us,gb,in")

    request_timeout_seconds: int = Field(default=20, ge=1)
    retry_max_attempts: int = Field(default=4, ge=1)
    retry_backoff_seconds: float = Field(default=2.0, ge=0)

    log_level: str = Field(default="INFO")
    log_dir: Path = Field(default=Path("./logs"))

    @field_validator("raw_data_dir", "log_dir", mode="before")
    @classmethod
    def _coerce_path(cls, v):
        return Path(v) if not isinstance(v, Path) else v

    @property
    def reddit_subreddit_list(self) -> List[str]:
        return [s.strip() for s in self.reddit_subreddits.split(",") if s.strip()]

    @property
    def app_store_country_list(self) -> List[str]:
        return [c.strip().lower() for c in self.app_store_countries.split(",") if c.strip()]

    @property
    def play_store_lang_list(self) -> List[str]:
        return [c.strip().lower() for c in self.play_store_langs.split(",") if c.strip()]

    @property
    def play_store_country_list(self) -> List[str]:
        return [c.strip().lower() for c in self.play_store_countries.split(",") if c.strip()]

    def ensure_directories(self) -> None:
        self.raw_data_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def reddit_enabled(self) -> bool:
        return bool(self.reddit_client_id and self.reddit_client_secret)


settings = Settings()
