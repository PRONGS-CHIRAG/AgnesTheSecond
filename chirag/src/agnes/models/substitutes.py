"""Pydantic contracts for Phase 4 substitute candidate generation."""

from __future__ import annotations

from datetime import datetime
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

SUBSTITUTES_SCHEMA_VERSION: Final[str] = "v1"

UnassignedReason = str  # one of: no_family, singleton_family, all_below_threshold


class CandidateFeatures(BaseModel):
    """Transparent per-signal features for a (source, candidate) pair."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    family_match: bool
    role_match: bool
    lexical_sim: float = Field(ge=0.0, le=1.0)
    embed_sim: float | None = Field(default=None, ge=0.0, le=1.0)
    supplier_overlap: float = Field(ge=0.0, le=1.0)
    co_company_overlap: float = Field(ge=0.0, le=1.0)
    missing_signals: list[str] = Field(default_factory=list)


class SubstituteCandidate(BaseModel):
    """One ranked substitute suggestion with explainable features."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_key: str
    candidate_key: str
    family: str | None
    roles: list[str] = Field(default_factory=list)
    score: float
    features: CandidateFeatures
    embedding_model: str | None = None
    taxonomy_version: str
    graph_schema_version: str
    schema_version: str = SUBSTITUTES_SCHEMA_VERSION


class TargetDiagnostics(BaseModel):
    """Diagnostics for one source material."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_key: str
    n_pool: int
    n_after_filter: int
    n_returned: int
    best_score: float | None = None
    reason: UnassignedReason | None = None


class SubstituteCandidateReport(BaseModel):
    """Aggregated report for a Phase 4 run."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = SUBSTITUTES_SCHEMA_VERSION
    taxonomy_version: str
    graph_schema_version: str
    generated_at: datetime
    embedding_model: str | None
    weights: dict[str, float]
    min_score: float
    top_k: int
    cross_family: bool
    n_targets: int
    n_with_candidates: int
    n_without_candidates: int
    avg_top_score: float | None = None
    duration_ms: int
    partial: bool = False
    targets: list[TargetDiagnostics] = Field(default_factory=list)
    candidates: list[SubstituteCandidate] = Field(default_factory=list)
