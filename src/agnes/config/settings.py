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

    phase4_top_k: int = Field(
        default=10,
        ge=1,
        description="Default top-K substitute candidates per target (Phase 4).",
    )
    phase4_min_score: float = Field(
        default=0.55,
        ge=0.0,
        le=1.0,
        description="Default minimum composite score for Phase 4 candidates.",
    )
    phase4_weights: str = Field(
        default=(
            '{"family":0.30,"role":0.15,"embed":0.35,'
            '"lexical":0.10,"supplier_overlap":0.10}'
        ),
        description=(
            "JSON blob of Phase 4 scoring weights. Missing keys fall back to defaults."
        ),
    )
    phase4_embedding_model: str = Field(
        default="gemini-embedding-001",
        description="Gemini embedding model id used by Phase 4.",
    )
    phase4_cross_family_default: bool = Field(
        default=False,
        description="Whether Phase 4 searches outside the source family by default.",
    )

    phase5_top_sources: int = Field(
        default=5,
        ge=0,
        description="Phase 5: max distinct source materials to enrich per run.",
    )
    phase5_per_source: int = Field(
        default=3,
        ge=0,
        description="Phase 5: max candidates enriched per source material.",
    )
    phase5_max_total: int = Field(
        default=25,
        ge=0,
        description="Phase 5: hard cap on *new* grounded API calls per run.",
    )
    phase5_grounded_model: str = Field(
        default="gemini-2.5-flash",
        description="Phase 5: Gemini model id used with the google_search tool.",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="AGNES_",
        extra="ignore",
    )
