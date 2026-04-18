"""Pydantic models for Phase 6.5 supply-risk reports.

Ports the 5 deterministic risk types from ``taim/insights/agnes_engine.py`` into
chirag-native versioned artifacts.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

RISK_SCHEMA_VERSION: Final[str] = "v1"

RiskSeverity = Literal["high", "medium", "low"]
RiskType = Literal[
    "single_source",
    "supplier_concentration",
    "critical_ingredient",
    "supplier_quality",
    "price_volatility",
]


class RiskItem(BaseModel):
    """One detected risk."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: RiskType
    severity: RiskSeverity
    key: str = Field(
        ...,
        description=(
            "Stable identifier for the risk subject: canonical ingredient base-name "
            "for ingredient risks, ``supplier:<id>`` for supplier risks."
        ),
    )
    label: str = Field(..., description="Human-readable name.")
    description: str
    recommendation: str
    score: float = Field(ge=0.0, le=1.0)
    n_companies_affected: int = 0
    n_products_affected: int = 0
    n_suppliers: int = 0
    evidence: list[str] = Field(default_factory=list)


class SupplyRiskReport(BaseModel):
    """Aggregated Phase 6.5 artifact."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = RISK_SCHEMA_VERSION
    taxonomy_version: str
    generated_at: datetime
    items: list[RiskItem] = Field(default_factory=list)
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_type: dict[str, int] = Field(default_factory=dict)
    n_total: int = 0
    partial: bool = False


__all__ = [
    "RISK_SCHEMA_VERSION",
    "RiskItem",
    "RiskSeverity",
    "RiskType",
    "SupplyRiskReport",
]
