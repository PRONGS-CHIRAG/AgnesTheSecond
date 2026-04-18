"""Procurement dashboard endpoints.

Surface the mock procurement tables (``Supplier_Rating``,
``Price_Benchmark``, ``Procurement_History``) through three read-only
endpoints:

* ``GET /api/procurement/overview``
* ``GET /api/procurement/savings``
* ``GET /api/procurement/suppliers``

All endpoints degrade gracefully when the procurement tables are absent —
they return ``partial=True`` with empty collections instead of 404s, so the
dashboard can render an informative empty state.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from agnes.config.settings import Settings
from agnes.data.db_loader import (
    get_engine,
    load_price_benchmarks,
    load_procurement_history,
    load_supplier_ratings,
    procurement_tables_present,
)
from agnes.data.queries import load_suppliers
from agnes.services.cost import (
    CostSignal,
    SupplierPricing,
    build_supplier_pricing,
    compute_cost_signal,
)

router = APIRouter(prefix="/api/procurement", tags=["procurement"])

_RM_SKU_RE = re.compile(r"^RM-C\d+-(?P<base>.+?)-[0-9a-f]{4,}$", re.IGNORECASE)


def _base_name(sku: str) -> str:
    """Extract the canonical base name from a raw-material SKU."""

    if not sku:
        return sku
    m = _RM_SKU_RE.match(sku)
    return (m.group("base").lower() if m else sku.lower()).strip()


def _humanize(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").title()


class TopSupplier(BaseModel):
    model_config = ConfigDict(extra="forbid")
    supplier_id: int
    supplier_name: str
    total_spend: float
    n_orders: int
    on_time_rate: float


class TopIngredient(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_name: str
    display_name: str
    total_spend: float
    n_orders: int
    n_suppliers: int


class ProcurementOverview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    partial: bool
    total_spend: float
    n_orders: int
    n_suppliers: int
    n_ingredients: int
    on_time_rate: float
    top_suppliers: list[TopSupplier]
    top_ingredients: list[TopIngredient]


class SavingsOpportunity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_name: str
    display_name: str
    spread_pct: float
    signal: float
    estimated_savings_usd: float
    best_supplier_id: int | None
    best_supplier_name: str | None
    best_supplier_price: float | None
    current_weighted_avg_price: float | None
    meets_gates: bool
    evidence: list[str] = Field(default_factory=list)


class SavingsReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    partial: bool
    n_ingredients_evaluated: int
    n_opportunities: int
    total_estimated_savings_usd: float
    opportunities: list[SavingsOpportunity]


class SupplierSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    supplier_id: int
    supplier_name: str
    total_spend: float
    n_orders: int
    n_ingredients: int
    on_time_rate: float
    avg_quality_pass_rate: float
    quality_score: float | None
    compliance_score: float | None
    reliability_score: float | None
    lead_time_days: int | None
    risk_tier: str | None
    certifications: list[str] = Field(default_factory=list)


class SuppliersReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    partial: bool
    n_suppliers: int
    suppliers: list[SupplierSummary]


def _empty_overview() -> ProcurementOverview:
    return ProcurementOverview(
        partial=True,
        total_spend=0.0,
        n_orders=0,
        n_suppliers=0,
        n_ingredients=0,
        on_time_rate=0.0,
        top_suppliers=[],
        top_ingredients=[],
    )


@router.get("/overview", response_model=ProcurementOverview)
def procurement_overview(request: Request) -> ProcurementOverview:
    settings: Settings = request.app.state.settings
    engine = get_engine(settings)
    if not procurement_tables_present(engine):
        return _empty_overview()

    supplier_df = load_suppliers(engine)
    supplier_names: dict[int, str] = {
        int(r.Id): str(r.Name) for r in supplier_df.itertuples()
    }

    product_sku_by_id: dict[int, str] = {}
    with engine.connect() as conn:
        for row in conn.execute(
            text("SELECT Id, SKU FROM Product WHERE Type = 'raw-material'")
        ):
            product_sku_by_id[int(row.Id)] = str(row.SKU)

    agg_supplier: dict[int, dict[str, Any]] = defaultdict(
        lambda: {"spend": 0.0, "orders": 0, "on_time": 0}
    )
    agg_ingredient: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"spend": 0.0, "orders": 0, "suppliers": set()}
    )
    total_spend = 0.0
    total_orders = 0
    total_on_time = 0

    for order in load_procurement_history(engine, settings):
        total_spend += order.TotalCost
        total_orders += 1
        total_on_time += 1 if order.OnTime else 0

        sa = agg_supplier[order.SupplierId]
        sa["spend"] += order.TotalCost
        sa["orders"] += 1
        sa["on_time"] += 1 if order.OnTime else 0

        sku = product_sku_by_id.get(order.ProductId, "")
        base = _base_name(sku) if sku else f"product-{order.ProductId}"
        ia = agg_ingredient[base]
        ia["spend"] += order.TotalCost
        ia["orders"] += 1
        ia["suppliers"].add(order.SupplierId)

    on_time_rate = (total_on_time / total_orders * 100.0) if total_orders else 0.0

    top_suppliers = sorted(
        agg_supplier.items(), key=lambda kv: kv[1]["spend"], reverse=True
    )[:10]
    top_suppliers_out = [
        TopSupplier(
            supplier_id=sid,
            supplier_name=supplier_names.get(sid, f"supplier-{sid}"),
            total_spend=round(d["spend"], 2),
            n_orders=int(d["orders"]),
            on_time_rate=round(
                (d["on_time"] / d["orders"] * 100.0) if d["orders"] else 0.0, 2
            ),
        )
        for sid, d in top_suppliers
    ]

    top_ingredients = sorted(
        agg_ingredient.items(), key=lambda kv: kv[1]["spend"], reverse=True
    )[:10]
    top_ingredients_out = [
        TopIngredient(
            base_name=base,
            display_name=_humanize(base),
            total_spend=round(d["spend"], 2),
            n_orders=int(d["orders"]),
            n_suppliers=len(d["suppliers"]),
        )
        for base, d in top_ingredients
    ]

    return ProcurementOverview(
        partial=False,
        total_spend=round(total_spend, 2),
        n_orders=total_orders,
        n_suppliers=len(agg_supplier),
        n_ingredients=len(agg_ingredient),
        on_time_rate=round(on_time_rate, 2),
        top_suppliers=top_suppliers_out,
        top_ingredients=top_ingredients_out,
    )


def _group_orders_by_base(
    orders_iter,
    *,
    product_sku_by_id: dict[int, str],
) -> dict[str, list[Any]]:
    by_base: dict[str, list[Any]] = defaultdict(list)
    for o in orders_iter:
        sku = product_sku_by_id.get(o.ProductId, "")
        if not sku:
            continue
        base = _base_name(sku)
        by_base[base].append(o)
    return by_base


@router.get("/savings", response_model=SavingsReport)
def procurement_savings(
    request: Request, min_signal: float = 0.0
) -> SavingsReport:
    settings: Settings = request.app.state.settings
    engine = get_engine(settings)
    if not procurement_tables_present(engine):
        return SavingsReport(
            partial=True,
            n_ingredients_evaluated=0,
            n_opportunities=0,
            total_estimated_savings_usd=0.0,
            opportunities=[],
        )

    supplier_df = load_suppliers(engine)
    supplier_names: dict[int, str] = {
        int(r.Id): str(r.Name) for r in supplier_df.itertuples()
    }
    ratings = load_supplier_ratings(engine, settings)
    benchmarks = load_price_benchmarks(engine, settings)

    product_sku_by_id: dict[int, str] = {}
    with engine.connect() as conn:
        for row in conn.execute(
            text("SELECT Id, SKU FROM Product WHERE Type = 'raw-material'")
        ):
            product_sku_by_id[int(row.Id)] = str(row.SKU)

    by_base = _group_orders_by_base(
        load_procurement_history(engine, settings),
        product_sku_by_id=product_sku_by_id,
    )

    opps: list[SavingsOpportunity] = []
    total_savings = 0.0
    for base, orders in by_base.items():
        pricings: list[SupplierPricing] = build_supplier_pricing(
            orders,
            ratings_by_supplier=ratings,
            supplier_names=supplier_names,
        )
        signal: CostSignal = compute_cost_signal(
            pricings,
            benchmark=benchmarks.get(base),
            ingredient_label=_humanize(base),
        )
        if signal.signal < min_signal:
            continue
        if not signal.meets_gates and signal.signal <= 0.0:
            continue
        opps.append(
            SavingsOpportunity(
                base_name=base,
                display_name=_humanize(base),
                spread_pct=signal.spread_pct,
                signal=signal.signal,
                estimated_savings_usd=signal.estimated_savings_usd,
                best_supplier_id=signal.best_supplier_id,
                best_supplier_name=signal.best_supplier_name,
                best_supplier_price=signal.best_supplier_price,
                current_weighted_avg_price=signal.current_weighted_avg_price,
                meets_gates=signal.meets_gates,
                evidence=signal.evidence,
            )
        )
        total_savings += signal.estimated_savings_usd

    opps.sort(key=lambda o: o.estimated_savings_usd, reverse=True)
    return SavingsReport(
        partial=False,
        n_ingredients_evaluated=len(by_base),
        n_opportunities=len(opps),
        total_estimated_savings_usd=round(total_savings, 2),
        opportunities=opps,
    )


@router.get("/suppliers", response_model=SuppliersReport)
def procurement_suppliers(request: Request) -> SuppliersReport:
    settings: Settings = request.app.state.settings
    engine = get_engine(settings)
    if not procurement_tables_present(engine):
        return SuppliersReport(partial=True, n_suppliers=0, suppliers=[])

    supplier_df = load_suppliers(engine)
    supplier_names: dict[int, str] = {
        int(r.Id): str(r.Name) for r in supplier_df.itertuples()
    }
    ratings = load_supplier_ratings(engine, settings)

    agg: dict[int, dict[str, Any]] = defaultdict(
        lambda: {
            "spend": 0.0,
            "orders": 0,
            "on_time": 0,
            "products": set(),
            "quality_sum": 0.0,
            "quality_n": 0,
        }
    )

    for o in load_procurement_history(engine, settings):
        d = agg[o.SupplierId]
        d["spend"] += o.TotalCost
        d["orders"] += 1
        d["on_time"] += 1 if o.OnTime else 0
        d["products"].add(o.ProductId)
        if o.QualityPassRate is not None:
            d["quality_sum"] += float(o.QualityPassRate)
            d["quality_n"] += 1

    rows: list[SupplierSummary] = []
    for sid, d in agg.items():
        rating = ratings.get(sid)
        n_orders = int(d["orders"])
        rows.append(
            SupplierSummary(
                supplier_id=sid,
                supplier_name=supplier_names.get(sid, f"supplier-{sid}"),
                total_spend=round(d["spend"], 2),
                n_orders=n_orders,
                n_ingredients=len(d["products"]),
                on_time_rate=round(
                    (d["on_time"] / n_orders * 100.0) if n_orders else 0.0, 2
                ),
                avg_quality_pass_rate=round(
                    (d["quality_sum"] / d["quality_n"]) if d["quality_n"] else 0.0,
                    2,
                ),
                quality_score=rating.QualityScore if rating else None,
                compliance_score=rating.ComplianceScore if rating else None,
                reliability_score=rating.ReliabilityScore if rating else None,
                lead_time_days=rating.LeadTimeDays if rating else None,
                risk_tier=rating.RiskTier if rating else None,
                certifications=list(rating.Certifications) if rating else [],
            )
        )

    rows.sort(key=lambda r: r.total_spend, reverse=True)
    return SuppliersReport(partial=False, n_suppliers=len(rows), suppliers=rows)


__all__ = ["router"]
