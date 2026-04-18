"""Pure deterministic supply-risk detection (Phase 6.5).

Ported from ``taim/insights/agnes_engine.py::assess_risks``. Inputs are minimal
aggregated views; no DB/LLM coupling. Each function returns ``list[RiskItem]``.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from agnes.models.procurement import PriceBenchmark, SupplierRating
from agnes.models.risk import RiskItem


@dataclass(frozen=True)
class SupplierInfo:
    """Lightweight supplier handle used by the risk service."""

    supplier_id: int
    name: str


@dataclass(frozen=True)
class IngredientProfile:
    """Aggregated view of one raw-material base_name.

    ``suppliers``: distinct suppliers (by id) that currently offer this
    ingredient at *any* company. ``n_companies`` and ``n_products`` reflect
    downstream usage (companies/products that BOM it).
    """

    base_name: str
    label: str
    suppliers: tuple[SupplierInfo, ...] = field(default_factory=tuple)
    n_companies: int = 0
    n_products: int = 0


def _ingredient_risk_item(
    *,
    risk_type: str,
    severity: str,
    profile: IngredientProfile,
    score: float,
    description: str,
    recommendation: str,
    evidence: list[str],
    n_suppliers: int | None = None,
) -> RiskItem:
    return RiskItem(
        type=risk_type,  # type: ignore[arg-type]
        severity=severity,  # type: ignore[arg-type]
        key=profile.base_name,
        label=profile.label,
        description=description,
        recommendation=recommendation,
        score=score,
        n_companies_affected=profile.n_companies,
        n_products_affected=profile.n_products,
        n_suppliers=n_suppliers if n_suppliers is not None else len(profile.suppliers),
        evidence=evidence,
    )


def single_source_risks(
    profiles: list[IngredientProfile],
) -> list[RiskItem]:
    """An ingredient used by >=2 companies but sourced from only 1 supplier."""
    out: list[RiskItem] = []
    for prof in profiles:
        if len(prof.suppliers) == 1 and prof.n_companies >= 2:
            sup = prof.suppliers[0]
            out.append(_ingredient_risk_item(
                risk_type="single_source",
                severity="high",
                profile=prof,
                score=1.0,
                description=(
                    f"{prof.label} is supplied by only {sup.name}, affecting "
                    f"{prof.n_companies} companies and {prof.n_products} products."
                ),
                recommendation=(
                    f"Qualify at least one additional supplier for {prof.label} "
                    "to mitigate single-source risk."
                ),
                evidence=[f"sole supplier: {sup.name} (id={sup.supplier_id})"],
            ))
    return out


def supplier_concentration_risks(
    profiles: list[IngredientProfile],
    supplier_names: dict[int, str],
) -> list[RiskItem]:
    """Suppliers that are the *sole* source of >=3 ingredients."""
    dominance: dict[int, dict[str, object]] = defaultdict(
        lambda: {"sole_ingredients": [], "total_ingredients": 0}
    )
    for prof in profiles:
        for sup in prof.suppliers:
            d = dominance[sup.supplier_id]
            d["total_ingredients"] = int(d["total_ingredients"]) + 1  # type: ignore[arg-type]
            if len(prof.suppliers) == 1:
                ingredients = d["sole_ingredients"]
                assert isinstance(ingredients, list)
                ingredients.append(prof.base_name)

    out: list[RiskItem] = []
    for sid, d in dominance.items():
        sole = list(d["sole_ingredients"])  # type: ignore[arg-type]
        sole_count = len(sole)
        if sole_count < 3:
            continue
        sup_name = supplier_names.get(sid, f"supplier-{sid}")
        severity = "high" if sole_count >= 10 else "medium"
        score = min(1.0, 0.3 + 0.07 * sole_count)
        preview = ", ".join(sole[:5])
        out.append(RiskItem(
            type="supplier_concentration",
            severity=severity,
            key=f"supplier:{sid}",
            label=sup_name,
            description=(
                f"{sup_name} is the sole supplier for {sole_count} ingredients. "
                "Loss of this supplier would create critical shortages."
            ),
            recommendation=(
                f"Develop alternative supplier relationships for the {sole_count} "
                f"ingredients solely sourced from {sup_name}."
            ),
            score=round(score, 3),
            n_suppliers=1,
            evidence=[
                f"sole source for: {preview}" + ("..." if sole_count > 5 else ""),
                f"total ingredients offered: {d['total_ingredients']}",
            ],
        ))
    return out


def critical_ingredient_risks(
    profiles: list[IngredientProfile],
) -> list[RiskItem]:
    """High downstream demand (>=5 companies) vs. thin supply (<=2 suppliers)."""
    out: list[RiskItem] = []
    for prof in profiles:
        n_sup = len(prof.suppliers)
        if prof.n_companies < 5 or n_sup > 2:
            continue
        ratio = prof.n_companies / max(n_sup, 1)
        if ratio < 4:
            continue
        out.append(_ingredient_risk_item(
            risk_type="critical_ingredient",
            severity="medium",
            profile=prof,
            score=min(1.0, 0.2 + 0.1 * ratio),
            description=(
                f"{prof.label} serves {prof.n_companies} companies but has only "
                f"{n_sup} supplier(s). Demand/supply ratio: {ratio:.1f}x"
            ),
            recommendation=(
                f"Qualify additional suppliers for {prof.label} to better balance "
                f"demand across {prof.n_companies} companies."
            ),
            evidence=[
                f"companies_using={prof.n_companies}",
                f"suppliers_offering={n_sup}",
                f"ratio={ratio:.1f}",
            ],
            n_suppliers=n_sup,
        ))
    return out


def supplier_quality_risks(
    ratings: dict[int, SupplierRating],
    supplier_names: dict[int, str],
    supplier_product_counts: dict[int, int],
) -> list[RiskItem]:
    """Suppliers classified ``high`` risk or with QualityScore < 80."""
    out: list[RiskItem] = []
    for sid, r in ratings.items():
        if not (r.RiskTier == "high" or r.QualityScore < 80):
            continue
        prod_count = supplier_product_counts.get(sid, 0)
        if prod_count <= 0:
            continue
        sup_name = supplier_names.get(sid, f"supplier-{sid}")
        severity = "high" if r.QualityScore < 70 else "medium"
        score = min(1.0, max(0.0, (100.0 - r.QualityScore) / 30.0))
        out.append(RiskItem(
            type="supplier_quality",
            severity=severity,
            key=f"supplier:{sid}",
            label=sup_name,
            description=(
                f"{sup_name} has a quality score of {r.QualityScore:.0f}/100 and "
                f"compliance score of {r.ComplianceScore:.0f}/100, classified as "
                f"{r.RiskTier}-risk. Supplies {prod_count} products."
            ),
            recommendation=(
                f"Conduct quality audit of {sup_name} and develop contingency "
                f"sourcing for their {prod_count} supplied products."
            ),
            score=round(score, 3),
            n_products_affected=prod_count,
            n_suppliers=1,
            evidence=[
                f"quality_score={r.QualityScore:.1f}",
                f"compliance_score={r.ComplianceScore:.1f}",
                f"reliability_score={r.ReliabilityScore:.1f}",
                f"risk_tier={r.RiskTier}",
            ],
        ))
    return out


def price_volatility_risks(
    profiles: list[IngredientProfile],
    benchmarks: dict[str, PriceBenchmark],
) -> list[RiskItem]:
    """Ingredients with volatility >= 25% affecting >=3 companies."""
    out: list[RiskItem] = []
    for prof in profiles:
        b = benchmarks.get(prof.base_name)
        if b is None:
            continue
        vol = b.PriceVolatility
        if vol < 0.25 or prof.n_companies < 3:
            continue
        out.append(_ingredient_risk_item(
            risk_type="price_volatility",
            severity="medium",
            profile=prof,
            score=min(1.0, vol * 2.0),
            description=(
                f"{prof.label} has {vol*100:.0f}% price volatility affecting "
                f"{prof.n_companies} companies. Avg price: ${b.AvgMarketPrice:.2f}/kg."
            ),
            recommendation=(
                f"Consider long-term contracts or hedging for {prof.label} to "
                "stabilize costs."
            ),
            evidence=[
                f"volatility={vol:.2f}",
                f"avg_market_price=${b.AvgMarketPrice:.2f}",
                f"range=${b.MinPrice:.2f}-${b.MaxPrice:.2f}",
            ],
        ))
    return out


def sort_risks(items: list[RiskItem]) -> list[RiskItem]:
    """Sort by severity (high first) then by n_companies_affected desc."""
    severity_rank = {"high": 0, "medium": 1, "low": 2}
    return sorted(
        items,
        key=lambda r: (
            severity_rank.get(r.severity, 3),
            -r.n_companies_affected,
            -r.score,
            r.key,
        ),
    )


__all__ = [
    "IngredientProfile",
    "SupplierInfo",
    "critical_ingredient_risks",
    "price_volatility_risks",
    "single_source_risks",
    "sort_risks",
    "supplier_concentration_risks",
    "supplier_quality_risks",
]
