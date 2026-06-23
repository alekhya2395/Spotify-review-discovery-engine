"""Configuration for the Phase 6 Streamlit dashboard."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_title: str = Field(default="Spotify Review Discovery Engine", validation_alias="PHASE6_APP_TITLE")
    default_card_limit: int = Field(default=53, ge=1, validation_alias="PHASE6_DEFAULT_CARD_LIMIT")
    default_search_k: int = Field(default=10, ge=1, le=50, validation_alias="PHASE6_DEFAULT_SEARCH_K")
    chat_context_k: int = Field(default=8, ge=1, le=20, validation_alias="PHASE6_CHAT_CONTEXT_K")
    enable_chat: bool = Field(default=True, validation_alias="PHASE6_ENABLE_CHAT")
    export_dir: Path = Field(default=Path("./data/exports"), validation_alias="PHASE6_EXPORT_DIR")

    groq_api_key: Optional[str] = Field(default=None, validation_alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.1-8b-instant", validation_alias="GROQ_MODEL")

    @property
    def export_dir_path(self) -> Path:
        self.export_dir.mkdir(parents=True, exist_ok=True)
        return self.export_dir


settings = Settings()
