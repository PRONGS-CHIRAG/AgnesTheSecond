"""Pydantic models for canonicalized raw materials and registry (Phase 2)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CanonicalMaterial(BaseModel):
    """One raw-material row after SKU parsing + family/role assignment."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    raw_product_id: int
    sku: str
    company_id: int
    normalized_name: str
    canonical_key: str
    ingredient_family: str
    functional_role: str
    confidence: float = Field(ge=0.0, le=1.0)
    missing_info: list[str] = Field(default_factory=list)
    parse_ok: bool
    taxonomy_version: str


class FamilyRoleAssignment(BaseModel):
    """LLM (or fallback) assignment for a single canonical key."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    canonical_key: str
    ingredient_family: str
    functional_role: str
    confidence: float = Field(ge=0.0, le=1.0)
    missing_info: list[str] = Field(default_factory=list)


class FamilyRoleBatchResponse(BaseModel):
    """Batch LLM response envelope for family/role inference."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    assignments: list[FamilyRoleAssignment]


class RegistryCoverage(BaseModel):
    """Coverage counters for a ``CanonicalRegistry``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    assigned: int
    unassigned: int
    parse_failed: int


class CanonicalRegistry(BaseModel):
    """All canonicalized raw materials plus bookkeeping."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    taxonomy_version: str
    generated_at: datetime
    unique_canonical_keys: int
    coverage: RegistryCoverage
    materials: list[CanonicalMaterial]

    def by_canonical_key(self) -> dict[str, list[CanonicalMaterial]]:
        """Group materials by ``canonical_key`` (stable order)."""
        out: dict[str, list[CanonicalMaterial]] = {}
        for m in self.materials:
            out.setdefault(m.canonical_key, []).append(m)
        return out

    def canonical_keys(self) -> list[str]:
        """Sorted list of unique canonical keys in the registry."""
        return sorted({m.canonical_key for m in self.materials})
