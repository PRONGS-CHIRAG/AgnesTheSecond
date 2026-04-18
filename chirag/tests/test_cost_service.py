"""Tests for the deterministic cost-savings service."""

from __future__ import annotations

from datetime import date

from agnes.models.procurement import PriceBenchmark, ProcurementOrder, SupplierRating
from agnes.services.cost import (
    COMPLIANCE_SCORE_THRESHOLD,
    QUALITY_SCORE_THRESHOLD,
    SIGNAL_FULL_SPREAD_PCT,
    SPREAD_PCT_THRESHOLD,
    SupplierPricing,
    build_supplier_pricing,
    compute_cost_signal,
)


def _pricing(
    sid: int,
    price: float,
    *,
    spend: float = 10_000.0,
    quality: float = 90.0,
    compliance: float = 90.0,
    on_time: float = 95.0,
    name: str | None = None,
) -> SupplierPricing:
    return SupplierPricing(
        supplier_id=sid,
        supplier_name=name or f"supplier-{sid}",
        avg_price=price,
        total_spend=spend,
        quality_score=quality,
        compliance_score=compliance,
        on_time_rate=on_time,
    )


def test_empty_inputs_return_neutral_signal() -> None:
    sig = compute_cost_signal([])
    assert sig.signal == 0.0
    assert sig.meets_gates is False
    assert "no_supplier_pricing" in sig.missing


def test_single_supplier_returns_neutral_signal() -> None:
    sig = compute_cost_signal([_pricing(1, 10.0)])
    assert sig.signal == 0.0
    assert sig.meets_gates is False
    assert "single_supplier_only" in sig.missing


def test_spread_below_threshold_fails_gate() -> None:
    # 10% spread — below 15% threshold
    sig = compute_cost_signal([_pricing(1, 9.0), _pricing(2, 10.0)])
    assert sig.spread_pct < SPREAD_PCT_THRESHOLD
    assert sig.meets_gates is False
    assert sig.signal == 0.0


def test_low_quality_cheapest_fails_gate() -> None:
    # 20% spread but cheapest has quality 70
    sig = compute_cost_signal(
        [
            _pricing(1, 8.0, quality=QUALITY_SCORE_THRESHOLD - 5),
            _pricing(2, 10.0),
        ]
    )
    assert sig.spread_pct >= SPREAD_PCT_THRESHOLD
    assert sig.meets_gates is False
    assert sig.signal == 0.0


def test_low_compliance_cheapest_fails_gate() -> None:
    sig = compute_cost_signal(
        [
            _pricing(1, 8.0, compliance=COMPLIANCE_SCORE_THRESHOLD - 5),
            _pricing(2, 10.0),
        ]
    )
    assert sig.meets_gates is False
    assert sig.signal == 0.0


def test_passing_signal_scales_linearly_and_saturates() -> None:
    # 20% spread → midway between 15% (signal=0) and 30% (signal=1)
    sig_mid = compute_cost_signal([_pricing(1, 8.0), _pricing(2, 10.0)])
    assert sig_mid.meets_gates is True
    assert 0.0 < sig_mid.signal < 1.0
    # 50% spread saturates
    sig_big = compute_cost_signal([_pricing(1, 5.0), _pricing(2, 10.0)])
    assert sig_big.signal == 1.0
    # 30% spread == saturation
    sig_edge = compute_cost_signal([_pricing(1, 7.0), _pricing(2, 10.0)])
    assert sig_edge.spread_pct >= SIGNAL_FULL_SPREAD_PCT
    assert sig_edge.signal == 1.0


def test_estimated_savings_is_conservative() -> None:
    # volume = spend/price => 10000/10 + 10000/8 = 1000 + 1250 = 2250
    # price delta = 2 USD; 50% adoption => 2250 * 2 * 0.5 = 2250
    sig = compute_cost_signal([_pricing(1, 8.0), _pricing(2, 10.0)])
    assert sig.estimated_savings_usd == 2250.0
    assert sig.best_supplier_id == 1
    assert sig.best_supplier_price == 8.0


def test_benchmark_evidence_appears_when_present() -> None:
    bench = PriceBenchmark(
        BaseName="stevia",
        AvgMarketPrice=9.0,
        MinPrice=7.0,
        MaxPrice=11.0,
        PriceVolatility=0.1,
        LastUpdated=date(2024, 1, 1),
    )
    sig = compute_cost_signal(
        [_pricing(1, 8.0), _pricing(2, 10.0)],
        benchmark=bench,
        ingredient_label="stevia",
    )
    assert any("benchmark" in line.lower() for line in sig.evidence)


def test_build_supplier_pricing_aggregates_orders() -> None:
    orders = [
        ProcurementOrder(
            Id=1,
            SupplierId=10,
            ProductId=100,
            CompanyId=1,
            OrderDate=date(2024, 1, 1),
            Quantity=100.0,
            UnitPrice=10.0,
            TotalCost=1000.0,
            OnTime=True,
            QualityPassRate=100.0,
        ),
        ProcurementOrder(
            Id=2,
            SupplierId=10,
            ProductId=100,
            CompanyId=1,
            OrderDate=date(2024, 2, 1),
            Quantity=100.0,
            UnitPrice=12.0,
            TotalCost=1200.0,
            OnTime=False,
            QualityPassRate=95.0,
        ),
        ProcurementOrder(
            Id=3,
            SupplierId=20,
            ProductId=100,
            CompanyId=1,
            OrderDate=date(2024, 1, 1),
            Quantity=100.0,
            UnitPrice=8.0,
            TotalCost=800.0,
            OnTime=True,
            QualityPassRate=100.0,
        ),
    ]
    ratings = {
        10: SupplierRating(
            SupplierId=10,
            QualityScore=85.0,
            ComplianceScore=80.0,
            ReliabilityScore=75.0,
            LeadTimeDays=14,
            MinOrderQty=100,
        ),
        20: SupplierRating(
            SupplierId=20,
            QualityScore=90.0,
            ComplianceScore=92.0,
            ReliabilityScore=88.0,
            LeadTimeDays=10,
            MinOrderQty=50,
        ),
    }
    names = {10: "A", 20: "B"}
    pricings = build_supplier_pricing(
        orders, ratings_by_supplier=ratings, supplier_names=names
    )
    assert [p.supplier_id for p in pricings] == [20, 10]
    p20 = next(p for p in pricings if p.supplier_id == 20)
    assert p20.avg_price == 8.0
    assert p20.quality_score == 90.0
    p10 = next(p for p in pricings if p.supplier_id == 10)
    assert p10.avg_price == 11.0  # (10+12)/2
    assert p10.total_spend == 2200.0
    assert p10.on_time_rate == 50.0
