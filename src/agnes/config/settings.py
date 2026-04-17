"""Environment-backed settings (AGNES_ prefix)."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment and optional `.env` file."""

    db_path: Path = Field(
        default=Path("data/raw/db.sqlite"),
        description="Path to challenge SQLite database.",
    )
    gemini_api_key: str | None = Field(
        default=None,
        description="Google Gemini API key (google-genai).",
    )
    gemini_model: str = Field(
        default="gemini-2.5-flash",
        description="Model id for Gemini API.",
    )
    cognee_llm_provider: str = Field(
        default="gemini",
        description="LLM provider name for Cognee (LiteLLM-style).",
    )
    cognee_data_root: Path = Field(
        default=Path(".cognee_data"),
        description="Local directory for Cognee storage during development.",
    )
    log_level: str = Field(default="INFO", description="Logging level.")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="AGNES_",
        extra="ignore",
    )
