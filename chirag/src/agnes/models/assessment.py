"""Pydantic contracts for Phase 6 context and compliance reasoning."""

from __future__ import annotations

from datetime import datetime
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from agnes.models.evidence import CitationRef, ClaimKey

ASSESSMENT_SCHEMA_VERSION: Final[str] = "v2"

RecommendationClass = Literal[
    "recommend",
    "recommend_with_caveats",
    "do_not_recommend",
    "insufficient_evidence",
]

DecisionPath = Literal["rules", "llm"]


class AssessmentContext(BaseModel):
    """One (company, product, source, candidate) tuple ready for scoring."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    company_id: int
    company_name: str | None = None
    finished_product_id: int
    finished_product_sku: str | None = None
    source_key: str
    candidate_key: str
    source_display_name: str
    candidate_display_name: str
    substitute_score: float | None = None


class SubstituteAssessment(BaseModel):
    """Structured verdict for one (company, product, source, candidate) tuple."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    company_id: int
    company_name: str | None = None
    finished_product_id: int
    finished_product_sku: str | None = None
    source_key: str
    candidate_key: str
    source_display_name: str
    candidate_display_name: str

    recommendation_class: RecommendationClass
    acceptability: float = Field(ge=0.0, le=1.0)
    missing_information: list[ClaimKey] = Field(default_factory=list)
    contradictions: list[ClaimKey] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    rationale: str

    decision_path: DecisionPath
    citations_used: list[CitationRef] = Field(default_factory=list)
    substitute_score: float | None = None

    schema_version: str = ASSESSMENT_SCHEMA_VERSION
    generated_at: datetime
    llm_model: str | None = None


class SubstituteAssessmentLLM(BaseModel):
    """LLM-facing subset of ``SubstituteAssessment`` (structured OpenAI JSON response)."""

    model_config = ConfigDict(extra="forbid")

    recommendation_class: RecommendationClass
    rationale: str
    caveats: list[str] = Field(default_factory=list)
    missing_information: list[ClaimKey] = Field(default_factory=list)


class AssessmentReport(BaseModel):
    """Aggregated report for a Phase 6 run."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = ASSESSMENT_SCHEMA_VERSION
    generated_at: datetime
    llm_model: str | None = None
    weights: dict[str, float]
    thresholds: dict[str, float]

    n_tuples: int = Field(ge=0)
    n_rules_decisions: int = Field(ge=0)
    n_llm_decisions: int = Field(ge=0)
    n_cache_hits: int = Field(ge=0)
    n_api_calls: int = Field(ge=0)
    n_failures: int = Field(default=0, ge=0)
    n_without_evidence: int = Field(default=0, ge=0)
    counts_by_class: dict[str, int] = Field(default_factory=dict)
    duration_ms: int = Field(ge=0)
    partial: bool = False
    items: list[SubstituteAssessment] = Field(default_factory=list)
