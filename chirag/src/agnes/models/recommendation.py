"""Pydantic contracts for Phase 7 recommendation engine."""

from __future__ import annotations

from datetime import datetime
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from agnes.models.evidence import CitationRef

RECOMMENDATION_SCHEMA_VERSION: Final[str] = "v3"

RecommendationGrade = Literal[
    "safe_to_consolidate",
    "likely_safe_review_required",
    "potential_substitute_insufficient_evidence",
    "not_recommended",
]

DecisionPath = Literal["rules", "llm"]


class SourcingSignals(BaseModel):
    """Structural sourcing signals derived from the challenge DB."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_supplier_count: int = Field(ge=0)
    candidate_supplier_count: int = Field(ge=0)
    shared_supplier_ids: list[int] = Field(default_factory=list)
    company_supplier_overlap: float = Field(ge=0.0, le=1.0)
    concentration_relief: float = Field(ge=0.0, le=1.0)
    missing_signals: list[str] = Field(default_factory=list)


class DimensionScores(BaseModel):
    """Prioritization-framework sub-scores surfaced per recommendation.

    Five dimensions that explicitly balance the tension between consolidation
    leverage and concentration risk. The weighted sum is the new ``final_score``.
    Every dimension is in ``[0, 1]`` — higher is better for the recommendation.

    ``supplier_diversification`` is the key load-bearing signal: it penalizes
    recommendations that leave the company single-sourced after consolidation.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    consolidation_benefit: float = Field(
        ge=0.0,
        le=1.0,
        description="Volume leverage gained by consolidating onto the candidate.",
    )
    evidence_confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Strength of Phase 5 grounded evidence backing the swap.",
    )
    compliance_fit: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "Regulatory + certification + functional safety. Penalizes "
            "high-weight contradictions."
        ),
    )
    supplier_diversification: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "Concentration-risk guard. Near 0 when consolidation leaves a "
            "single supplier; near 1 when multiple suppliers remain."
        ),
    )
    switching_feasibility: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "How actionable the swap is in practice — existing supplier "
            "relationships shorten onboarding."
        ),
    )


class SourcingRecommendation(BaseModel):
    """One per-tuple recommendation row."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    company_id: int
    company_name: str | None = None
    finished_product_id: int
    finished_product_sku: str | None = None
    source_key: str
    candidate_key: str
    source_display_name: str
    candidate_display_name: str

    recommendation_grade: RecommendationGrade
    final_score: float = Field(ge=0.0, le=1.0)
    acceptability: float = Field(ge=0.0, le=1.0)
    substitute_score: float | None = None
    sourcing_benefit: float = Field(ge=0.0, le=1.0)
    signals: SourcingSignals
    dimension_scores: DimensionScores
    concentration_risk_downgrade: bool = Field(
        default=False,
        description=(
            "True when the monopoly-risk veto downgraded this row "
            "(supplier_diversification below the configured floor)."
        ),
    )

    current_suppliers: list[str] = Field(default_factory=list)
    recommended_suppliers: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    review_required: bool
    tradeoff_summary: str

    citations: list[CitationRef] = Field(default_factory=list)
    decision_path: DecisionPath
    schema_version: str = RECOMMENDATION_SCHEMA_VERSION
    generated_at: datetime
    llm_model: str | None = None

    def row_key(self) -> str:
        """Stable identifier for a per-tuple row (used by opportunities)."""
        return (
            f"{self.company_id}|{self.finished_product_id}|"
            f"{self.source_key}|{self.candidate_key}"
        )


class ConsolidationOpportunity(BaseModel):
    """Cluster-level rollup keyed by ``source_key``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_key: str
    source_display_name: str
    best_candidate_key: str
    best_candidate_display_name: str

    n_products_covered: int = Field(ge=0)
    n_companies_covered: int = Field(ge=0)
    aggregate_final_score: float = Field(ge=0.0, le=1.0)
    aggregate_sourcing_benefit: float = Field(ge=0.0, le=1.0)
    aggregate_dimension_scores: DimensionScores = Field(
        description="Mean of each DimensionScores field across the chosen candidate's rows."
    )
    any_concentration_risk_downgrade: bool = False
    recommendation_grade: RecommendationGrade

    unique_current_suppliers: list[str] = Field(default_factory=list)
    unique_recommended_suppliers: list[str] = Field(default_factory=list)
    review_required: bool
    tradeoff_summary: str
    risk_notes: list[str] = Field(default_factory=list)
    top_row_keys: list[str] = Field(default_factory=list)

    decision_path: DecisionPath = "rules"
    schema_version: str = RECOMMENDATION_SCHEMA_VERSION
    generated_at: datetime
    llm_model: str | None = None


class RecommendationReport(BaseModel):
    """Aggregated report for a Phase 7 run."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = RECOMMENDATION_SCHEMA_VERSION
    generated_at: datetime
    llm_model: str | None = None
    weights: dict[str, float]
    thresholds: dict[str, float]

    n_tuples: int = Field(ge=0)
    n_opportunities: int = Field(ge=0)
    n_cache_hits: int = Field(ge=0)
    n_api_calls: int = Field(ge=0)
    n_failures: int = Field(default=0, ge=0)
    counts_by_grade: dict[str, int] = Field(default_factory=dict)
    duration_ms: int = Field(ge=0)
    partial: bool = False

    items: list[SourcingRecommendation] = Field(default_factory=list)
    opportunities: list[ConsolidationOpportunity] = Field(default_factory=list)
