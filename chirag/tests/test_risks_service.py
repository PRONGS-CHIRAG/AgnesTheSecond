"""Tests for the deterministic supply-risk service (Stage D)."""

from __future__ import annotations

from agnes.models.procurement import PriceBenchmark, SupplierRating
from agnes.services.risk import (
    IngredientProfile,
    SupplierInfo,
    critical_ingredient_risks,
    price_volatility_risks,
    single_source_risks,
    sort_risks,
    supplier_concentration_risks,
    supplier_quality_risks,
)


def _profile(
    base_name: str,
    *,
    suppliers: list[tuple[int, str]],
    n_companies: int,
    n_products: int,
) -> IngredientProfile:
    return IngredientProfile(
        base_name=base_name,
        label=base_name.replace("-", " ").title(),
        suppliers=tuple(SupplierInfo(s, n) for s, n in suppliers),
        n_companies=n_companies,
        n_products=n_products,
    )


def test_single_source_high_severity() -> None:
    profs = [
        _profile("whey-protein", suppliers=[(1, "Acme")], n_companies=3, n_products=5),
        _profile(  # 2 suppliers -> not single source
            "stevia", suppliers=[(1, "Acme"), (2, "Beta")],
            n_companies=3, n_products=5,
        ),
        _profile(  # 1 supplier but only 1 company -> ignored
            "boron", suppliers=[(3, "Gamma")], n_companies=1, n_products=1,
        ),
    ]
    out = single_source_risks(profs)
    assert len(out) == 1
    assert out[0].type == "single_source"
    assert out[0].severity == "high"
    assert out[0].key == "whey-protein"


def test_supplier_concentration_flags_dominance() -> None:
    p1 = _profile("a", suppliers=[(1, "Acme")], n_companies=2, n_products=2)
    p2 = _profile("b", suppliers=[(1, "Acme")], n_companies=2, n_products=2)
    p3 = _profile("c", suppliers=[(1, "Acme")], n_companies=2, n_products=2)
    p4 = _profile("d", suppliers=[(1, "Acme"), (2, "Beta")],
                  n_companies=2, n_products=2)
    supplier_names = {1: "Acme", 2: "Beta"}
    out = supplier_concentration_risks([p1, p2, p3, p4], supplier_names)
    assert len(out) == 1
    assert out[0].key == "supplier:1"
    assert out[0].type == "supplier_concentration"


def test_critical_ingredient_thresholds() -> None:
    profs = [
        _profile("a", suppliers=[(1, "Acme"), (2, "Beta")],
                 n_companies=10, n_products=15),
        _profile("b", suppliers=[(1, "Acme"), (2, "Beta"), (3, "Gamma")],
                 n_companies=10, n_products=15),
    ]
    out = critical_ingredient_risks(profs)
    keys = {r.key for r in out}
    assert "a" in keys
    assert "b" not in keys


def test_supplier_quality_ignored_when_no_products() -> None:
    ratings = {
        1: SupplierRating(
            SupplierId=1, QualityScore=60.0, ComplianceScore=70.0,
            ReliabilityScore=70.0, LeadTimeDays=14, MinOrderQty=100,
            RiskTier="high",
        ),
        2: SupplierRating(
            SupplierId=2, QualityScore=92.0, ComplianceScore=92.0,
            ReliabilityScore=92.0, LeadTimeDays=14, MinOrderQty=100,
            RiskTier="low",
        ),
    }
    names = {1: "Acme", 2: "Beta"}
    out = supplier_quality_risks(ratings, names, {1: 5, 2: 5})
    assert len(out) == 1
    assert out[0].severity == "high"
    assert out[0].key == "supplier:1"


def test_price_volatility_gates_apply() -> None:
    profs = [
        _profile("a", suppliers=[(1, "Acme"), (2, "Beta")],
                 n_companies=5, n_products=5),
        _profile("b", suppliers=[(1, "Acme")],
                 n_companies=2, n_products=2),
    ]
    benchmarks = {
        "a": PriceBenchmark(BaseName="a", AvgMarketPrice=20.0, MinPrice=15.0,
                            MaxPrice=25.0, PriceVolatility=0.3),
        "b": PriceBenchmark(BaseName="b", AvgMarketPrice=10.0, MinPrice=9.0,
                            MaxPrice=11.0, PriceVolatility=0.05),
    }
    out = price_volatility_risks(profs, benchmarks)
    assert len(out) == 1
    assert out[0].key == "a"


def test_sort_puts_high_severity_first() -> None:
    highs = single_source_risks([
        _profile("x", suppliers=[(1, "Acme")], n_companies=5, n_products=5),
    ])
    mediums = critical_ingredient_risks([
        _profile("y", suppliers=[(1, "Acme")], n_companies=6, n_products=6),
    ])
    merged = sort_risks(highs + mediums)
    assert merged[0].severity == "high"
    assert merged[-1].severity == "medium"
