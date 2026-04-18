"""Pydantic contracts for Phase 5 external evidence enrichment."""

from __future__ import annotations

from datetime import datetime
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

EVIDENCE_SCHEMA_VERSION: Final[str] = "v2"

ClaimKey = Literal[
    "functional_equivalence",
    "certification",
    "regulatory",
    "typical_suppliers",
    "quality_sensory",
    "price_availability",
]

ClaimPolarity = Literal["supports", "contradicts", "mixed", "unknown"]

GroundingStrength = Literal["grounded", "parametric"]


class CitationRef(BaseModel):
    """One external source cited for an evidence claim."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    url: str
    title: str | None = None
    domain: str | None = None
    retrieved_at: datetime


class EvidenceClaim(BaseModel):
    """One structured, citation-aware claim about a (source, candidate) pair."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: ClaimKey
    value: str
    polarity: ClaimPolarity
    confidence: float = Field(ge=0.0, le=1.0)
    citations: list[CitationRef] = Field(default_factory=list)
    grounding_strength: GroundingStrength


class SubstituteEvidence(BaseModel):
    """All evidence gathered for one (source, candidate) substitute pair."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_key: str
    candidate_key: str
    claims: list[EvidenceClaim] = Field(default_factory=list)
    n_citations: int = Field(ge=0)
    any_contradictions: bool
    retrieved_at: datetime
    llm_model: str
    schema_version: str = EVIDENCE_SCHEMA_VERSION


class SubstituteEvidenceLLM(BaseModel):
    """
    LLM-facing subset of ``SubstituteEvidence``. The grounded extraction prompt
    returns this shape; the enricher wraps it with server-side bookkeeping
    (``retrieved_at``, ``llm_model``, ``schema_version``).
    """

    model_config = ConfigDict(extra="forbid")

    claims: list[EvidenceClaim] = Field(default_factory=list)


class EvidenceReport(BaseModel):
    """Aggregated report for a Phase 5 run."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = EVIDENCE_SCHEMA_VERSION
    generated_at: datetime
    llm_model: str
    n_sources: int = Field(ge=0)
    n_pairs: int = Field(ge=0)
    n_cache_hits: int = Field(ge=0)
    n_api_calls: int = Field(ge=0)
    n_failures: int = Field(default=0, ge=0)
    duration_ms: int = Field(ge=0)
    partial: bool = False
    items: list[SubstituteEvidence] = Field(default_factory=list)
