"""Round-trip tests for the procurement Pydantic models."""

from __future__ import annotations

from datetime import date

import pytest

from agnes.models.procurement import (
    PROCUREMENT_SCHEMA_VERSION,
    PriceBenchmark,
    ProcurementOrder,
    SupplierRating,
)


def test_schema_version_is_v1() -> None:
    assert PROCUREMENT_SCHEMA_VERSION == "v1"


def test_supplier_rating_round_trip() -> None:
    payload = {
        "SupplierId": 42,
        "QualityScore": 90.5,
        "ComplianceScore": 88.0,
        "ReliabilityScore": 91.2,
        "LeadTimeDays": 14,
        "MinOrderQty": 500,
        "Certifications": ("GMP", "ISO-22000"),
        "LastAuditDate": date(2025, 6, 1),
        "RiskTier": "low",
    }
    rating = SupplierRating(**payload)
    assert rating.RiskTier == "low"
    assert rating.Certifications == ("GMP", "ISO-22000")
    assert rating.model_dump()["QualityScore"] == 90.5


def test_supplier_rating_clamps_via_validation() -> None:
    with pytest.raises(ValueError):
        SupplierRating(
            SupplierId=1,
            QualityScore=120.0,
            ComplianceScore=80.0,
            ReliabilityScore=80.0,
            LeadTimeDays=10,
            MinOrderQty=100,
        )


def test_price_benchmark_defaults() -> None:
    pb = PriceBenchmark(
        BaseName="whey-protein",
        AvgMarketPrice=20.5,
        MinPrice=18.0,
        MaxPrice=23.0,
        PriceVolatility=0.12,
    )
    assert pb.LastUpdated is None
    assert pb.PriceVolatility == 0.12


def test_procurement_order_defaults() -> None:
    order = ProcurementOrder(
        Id=1, SupplierId=5, ProductId=10, CompanyId=3,
        OrderDate=date(2025, 1, 1),
        Quantity=100.0, UnitPrice=10.0, TotalCost=1000.0,
        QualityPassRate=95.0,
    )
    assert order.Currency == "USD"
    assert order.OnTime is True
    assert order.DeliveryDate is None
