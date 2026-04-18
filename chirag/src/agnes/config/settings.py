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
    openai_api_key: str | None = Field(
        default=None,
        description="OpenAI API key (used by the openai SDK for all LLM + embedding calls).",
    )
    openai_model: str = Field(
        default="gpt-4o-mini",
        description="Default chat model id used for smoke pings and generic LLM calls.",
    )
    tavily_api_key: str | None = Field(
        default=None,
        description=(
            "Tavily Search API key for Phase 5 grounded search_web tool. "
            "Required when Phase 5 needs to enrich new source/candidate pairs."
        ),
    )
    cogwit_api_key: str | None = Field(
        default=None,
        description=(
            "Cognee Cloud API key (used by cogwit-sdk). "
            "Falls back to the COGWIT_API_KEY env var when AGNES_COGWIT_API_KEY is unset."
        ),
    )
    cogwit_dataset: str = Field(
        default="agnes",
        description="Default Cognee Cloud dataset name for ingest / smoke tests.",
    )
    cogwit_base_url: str | None = Field(
        default=None,
        description=(
            "Optional override for the Cognee Cloud base URL. "
            "When set, exported as COGWIT_API_BASE so cogwit-sdk picks it up."
        ),
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
        default="text-embedding-3-small",
        description="OpenAI embedding model id used by Phase 4.",
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
        default="gpt-4o-mini",
        description="Phase 5: OpenAI chat model id used with the search_web function-calling tool.",
    )

    phase6_claim_weights: str = Field(
        default=(
            '{"functional_equivalence":0.35,"regulatory":0.25,'
            '"certification":0.15,"quality_sensory":0.10,'
            '"price_availability":0.10,"typical_suppliers":0.05}'
        ),
        description=(
            "Phase 6: JSON blob of per-claim weights used by the deterministic "
            "acceptability scorer. Missing keys are treated as weight 0."
        ),
    )
    phase6_accept_threshold: float = Field(
        default=0.75,
        ge=0.0,
        le=1.0,
        description="Phase 6: acceptability >= threshold => 'recommend'.",
    )
    phase6_reject_threshold: float = Field(
        default=0.35,
        ge=0.0,
        le=1.0,
        description="Phase 6: acceptability <= threshold => 'do_not_recommend'.",
    )
    phase6_min_grounded_claims: int = Field(
        default=2,
        ge=0,
        description=(
            "Phase 6: below this many grounded claims the tuple is "
            "'insufficient_evidence'."
        ),
    )
    phase6_max_llm_calls: int = Field(
        default=25,
        ge=0,
        description="Phase 6: hard cap on new structured-LLM calls per run.",
    )
    phase6_llm_model: str = Field(
        default="gpt-4o-mini",
        description="Phase 6: OpenAI chat model id used for the structured JSON fallback.",
    )

    phase7_prioritization_weights: str = Field(
        default=(
            '{"consolidation_benefit":0.35,"evidence_confidence":0.25,'
            '"compliance_fit":0.20,"supplier_diversification":0.10,'
            '"switching_feasibility":0.10}'
        ),
        description=(
            "Phase 7: JSON blob of weights for the 5-dimension prioritization "
            "framework. Must sum to ~1.0; missing keys fall back to defaults."
        ),
    )
    phase7_safe_threshold: float = Field(
        default=0.70,
        ge=0.0,
        le=1.0,
        description="Phase 7: final_score >= threshold maps to 'safe_to_consolidate'.",
    )
    phase7_reject_threshold: float = Field(
        default=0.30,
        ge=0.0,
        le=1.0,
        description="Phase 7: final_score <= threshold maps to 'not_recommended'.",
    )
    phase7_diversification_floor: float = Field(
        default=0.30,
        ge=0.0,
        le=1.0,
        description=(
            "Phase 7: supplier_diversification below this floor downgrades a "
            "'safe_to_consolidate' grade to 'likely_safe_review_required' "
            "(the anti-monopoly veto)."
        ),
    )
    phase7_top_n_polish: int = Field(
        default=5,
        ge=0,
        description="Phase 7: number of top opportunities to polish with the LLM.",
    )
    phase7_max_llm_calls: int = Field(
        default=10,
        ge=0,
        description="Phase 7: hard cap on new LLM polish calls per run.",
    )
    phase7_llm_model: str = Field(
        default="gpt-4o-mini",
        description="Phase 7: OpenAI chat model id used for the optional polish pass.",
    )

    usitc_api_token: str | None = Field(
        default=None,
        description=(
            "USITC DataWeb API bearer token (JWT). Register + copy from "
            "https://dataweb.usitc.gov. Required for live price fetches; "
            "tests run offline without it."
        ),
    )
    usitc_base_url: str = Field(
        default="https://datawebws.usitc.gov/dataweb",
        description="USITC DataWeb base URL; runReport lives at {base}/api/v2/report2/runReport.",
    )
    usitc_default_year: str = Field(
        default="2023",
        description="Default trade year queried when the CLI does not supply --year.",
    )
    usitc_timeout_seconds: float = Field(
        default=60.0,
        ge=1.0,
        description=(
            "Per-request timeout for the DataWeb runReport endpoint. Kept generous "
            "since aggregate trade queries can take tens of seconds server-side."
        ),
    )
    usitc_cache_path: Path = Field(
        default=Path(".cache/usitc_prices.json"),
        description="On-disk JSON cache for DataWeb responses, keyed by (hts,year,trade_type).",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="AGNES_",
        extra="ignore",
    )
