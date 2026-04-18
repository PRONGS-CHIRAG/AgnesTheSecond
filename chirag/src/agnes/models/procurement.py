"""Pydantic models for the procurement / supplier-rating / price-benchmark tables.

These are the chirag-side counterparts of the three tables originally introduced
by ``taim/generate_mock_data.py``. Each model is a plain row shape (no business
logic) so downstream services (risk, cost) stay pure.
"""

from __future__ import annotations

from datetime import date
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

PROCUREMENT_SCHEMA_VERSION: Final[str] = "v1"

RiskTier = Literal["low", "medium", "high"]


class SupplierRating(BaseModel):
    """Row from the ``Supplier_Rating`` table.

    ``Certifications`` is stored as a comma-separated string on disk but is
    exposed here as a list for ergonomic downstream consumption.
    """

    model_config = ConfigDict(frozen=True)

    SupplierId: int = Field(..., description="FK to Supplier.Id")
    QualityScore: float = Field(..., ge=0.0, le=100.0)
    ComplianceScore: float = Field(..., ge=0.0, le=100.0)
    ReliabilityScore: float = Field(..., ge=0.0, le=100.0)
    LeadTimeDays: int = Field(..., ge=0)
    MinOrderQty: int = Field(..., ge=0)
    Certifications: tuple[str, ...] = Field(default_factory=tuple)
    LastAuditDate: date | None = None
    RiskTier: RiskTier = "medium"


class PriceBenchmark(BaseModel):
    """Row from the ``Price_Benchmark`` table (one per canonical base name)."""

    model_config = ConfigDict(frozen=True)

    BaseName: str
    AvgMarketPrice: float = Field(..., ge=0.0)
    MinPrice: float = Field(..., ge=0.0)
    MaxPrice: float = Field(..., ge=0.0)
    PriceVolatility: float = Field(..., ge=0.0)
    LastUpdated: date | None = None


class ProcurementOrder(BaseModel):
    """Row from the ``Procurement_History`` table."""

    model_config = ConfigDict(frozen=True)

    Id: int
    SupplierId: int
    ProductId: int
    CompanyId: int
    OrderDate: date
    DeliveryDate: date | None = None
    Quantity: float = Field(..., ge=0.0)
    UnitPrice: float = Field(..., ge=0.0)
    TotalCost: float = Field(..., ge=0.0)
    Currency: str = "USD"
    OnTime: bool = True
    QualityPassRate: float = Field(..., ge=0.0, le=100.0)


__all__ = [
    "PROCUREMENT_SCHEMA_VERSION",
    "PriceBenchmark",
    "ProcurementOrder",
    "RiskTier",
    "SupplierRating",
]
