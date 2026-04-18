"""Deterministic cost-savings signal for Phase 7 recommendations.

Ports the ``cost_optimization`` logic from ``taim/insights/agnes_engine.py`` into
a pure, testable service. The core gate from taim is preserved verbatim:

    spread_pct = (most_expensive.avg - cheapest.avg) / most_expensive.avg * 100
    # Only flag significant price spreads with acceptable quality/compliance
    if spread_pct >= 15 and cheapest.quality >= 75 and cheapest.compliance >= 75:
        ...

The public output (:class:`CostSignal`) exposes:

* ``signal`` in ``[0, 1]`` — ready to drop into the Phase 7 scorer alongside
  ``sourcing_benefit``.
* ``estimated_savings_usd`` — conservative (50% volume adoption) savings
  projection used for the opportunities table.
* ``meets_gates`` — the boolean taim used before emitting a cost recommendation.
* ``evidence`` — human-readable lines ready to append to
  ``SourcingRecommendation.caveats``.

When inputs are missing (no procurement history, no supplier pricing) we return
a neutral :class:`CostSignal` with ``signal=0.0`` and ``missing=["…"]`` rather
than raising — Phase 7 must degrade gracefully without procurement data.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Final

from agnes.models.procurement import PriceBenchmark, ProcurementOrder, SupplierRating

SPREAD_PCT_THRESHOLD: Final[float] = 15.0
QUALITY_SCORE_THRESHOLD: Final[float] = 75.0
COMPLIANCE_SCORE_THRESHOLD: Final[float] = 75.0
VOLUME_ADOPTION_FACTOR: Final[float] = 0.5  # conservative: 50% volume shifts
SIGNAL_FULL_SPREAD_PCT: Final[float] = 30.0  # spread at which signal saturates to 1.0


@dataclass(frozen=True)
class SupplierPricing:
    """Per-supplier aggregated pricing slice for one ingredient."""

    supplier_id: int
    supplier_name: str
    avg_price: float
    total_spend: float
    quality_score: float
    compliance_score: float
    on_time_rate: float

    def qualifies(self) -> bool:
        return (
            self.quality_score >= QUALITY_SCORE_THRESHOLD
            and self.compliance_score >= COMPLIANCE_SCORE_THRESHOLD
        )


@dataclass(frozen=True)
class CostSignal:
    """Output of :func:`compute_cost_signal`."""

    signal: float
    estimated_savings_usd: float
    spread_pct: float
    meets_gates: bool
    best_supplier_id: int | None = None
    best_supplier_name: str | None = None
    best_supplier_price: float | None = None
    current_weighted_avg_price: float | None = None
    evidence: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


def _weighted_avg_price(pricings: list[SupplierPricing]) -> float:
    total_spend = sum(p.total_spend for p in pricings)
    if total_spend <= 0.0:
        prices = [p.avg_price for p in pricings if p.avg_price > 0.0]
        return sum(prices) / len(prices) if prices else 0.0
    weighted = sum(p.avg_price * p.total_spend for p in pricings if p.avg_price > 0.0)
    return weighted / total_spend if total_spend > 0.0 else 0.0


def _total_volume(pricings: list[SupplierPricing]) -> float:
    vol = 0.0
    for p in pricings:
        if p.avg_price > 0.0:
            vol += p.total_spend / p.avg_price
    return vol


def build_supplier_pricing(
    orders: Iterable[ProcurementOrder],
    *,
    ratings_by_supplier: dict[int, SupplierRating],
    supplier_names: dict[int, str],
) -> list[SupplierPricing]:
    """Aggregate raw :class:`ProcurementOrder` rows into one row per supplier.

    Averages ``UnitPrice`` across orders, sums ``TotalCost``, and joins the
    static :class:`SupplierRating` for the quality/compliance gates.
    """

    agg: dict[int, dict[str, float]] = {}
    on_time_counts: dict[int, list[int]] = {}
    for o in orders:
        bucket = agg.setdefault(
            o.SupplierId,
            {"prices": 0.0, "n_prices": 0, "total_spend": 0.0},
        )
        if o.UnitPrice > 0.0:
            bucket["prices"] += o.UnitPrice
            bucket["n_prices"] += 1
        bucket["total_spend"] += o.TotalCost
        on_time_counts.setdefault(o.SupplierId, []).append(1 if o.OnTime else 0)

    out: list[SupplierPricing] = []
    for sid, b in agg.items():
        rating = ratings_by_supplier.get(sid)
        quality = rating.QualityScore if rating is not None else 0.0
        compliance = rating.ComplianceScore if rating is not None else 0.0
        flags = on_time_counts.get(sid, [])
        on_time_rate = (sum(flags) / len(flags) * 100.0) if flags else 0.0
        n = b["n_prices"] or 1
        out.append(
            SupplierPricing(
                supplier_id=sid,
                supplier_name=supplier_names.get(sid, f"supplier-{sid}"),
                avg_price=round(b["prices"] / n, 4) if b["n_prices"] else 0.0,
                total_spend=round(b["total_spend"], 2),
                quality_score=quality,
                compliance_score=compliance,
                on_time_rate=round(on_time_rate, 2),
            )
        )
    out.sort(key=lambda p: p.avg_price)
    return out


def compute_cost_signal(
    pricings: list[SupplierPricing],
    *,
    benchmark: PriceBenchmark | None = None,
    ingredient_label: str | None = None,
) -> CostSignal:
    """Compute the taim cost-savings signal for one ingredient.

    Strategy mirrors taim's cost-optimization branch:
        * Sort supplier pricing ascending by ``avg_price``.
        * Compute ``spread_pct`` vs the most-expensive supplier.
        * Gate on spread >= 15% AND cheapest qualifies (quality + compliance).
        * Project conservative savings at 50% volume adoption.

    When the gate fails or inputs are insufficient, ``signal=0.0`` and
    ``meets_gates=False`` — the scorer should treat this as "no useful signal"
    rather than as a negative.
    """

    missing: list[str] = []
    evidence: list[str] = []
    label = ingredient_label or "ingredient"

    if not pricings or len(pricings) < 2:
        if not pricings:
            missing.append("no_supplier_pricing")
        else:
            missing.append("single_supplier_only")
        return CostSignal(
            signal=0.0,
            estimated_savings_usd=0.0,
            spread_pct=0.0,
            meets_gates=False,
            missing=missing,
        )

    ordered = sorted(pricings, key=lambda p: p.avg_price)
    cheapest = ordered[0]
    most_expensive = ordered[-1]
    if cheapest.avg_price <= 0.0 or most_expensive.avg_price <= 0.0:
        return CostSignal(
            signal=0.0,
            estimated_savings_usd=0.0,
            spread_pct=0.0,
            meets_gates=False,
            missing=["zero_priced_supplier"],
        )

    spread_pct = (
        (most_expensive.avg_price - cheapest.avg_price) / most_expensive.avg_price * 100.0
    )
    weighted_avg = _weighted_avg_price(ordered)
    total_volume = _total_volume(ordered)
    est_savings = max(
        0.0,
        (most_expensive.avg_price - cheapest.avg_price)
        * total_volume
        * VOLUME_ADOPTION_FACTOR,
    )

    meets_gates = (
        spread_pct >= SPREAD_PCT_THRESHOLD
        and cheapest.qualifies()
    )

    if meets_gates:
        # Signal grows linearly from 0 at 15% spread to 1.0 at 30% spread,
        # saturating thereafter — matches taim's medium/low priority cutoff.
        span = max(SIGNAL_FULL_SPREAD_PCT - SPREAD_PCT_THRESHOLD, 1e-9)
        signal = max(
            0.0,
            min(1.0, (spread_pct - SPREAD_PCT_THRESHOLD) / span),
        )
    else:
        signal = 0.0

    evidence.append(
        f"Cheapest qualified supplier: {cheapest.supplier_name} at "
        f"${cheapest.avg_price:.2f} (quality {cheapest.quality_score:.0f}, "
        f"compliance {cheapest.compliance_score:.0f})."
    )
    evidence.append(
        f"Most expensive: {most_expensive.supplier_name} at "
        f"${most_expensive.avg_price:.2f} — spread {spread_pct:.1f}%."
    )
    if benchmark is not None and benchmark.AvgMarketPrice > 0.0:
        delta_pct = (
            (weighted_avg - benchmark.AvgMarketPrice) / benchmark.AvgMarketPrice * 100.0
            if benchmark.AvgMarketPrice
            else 0.0
        )
        direction = "above" if delta_pct > 0 else "below"
        evidence.append(
            f"{label.title()} current weighted-avg price ${weighted_avg:.2f} is "
            f"{abs(delta_pct):.1f}% {direction} market benchmark "
            f"(${benchmark.AvgMarketPrice:.2f})."
        )
    if not meets_gates:
        if spread_pct < SPREAD_PCT_THRESHOLD:
            evidence.append(
                f"Gate failed: spread {spread_pct:.1f}% < {SPREAD_PCT_THRESHOLD:.0f}% threshold."
            )
        elif not cheapest.qualifies():
            evidence.append(
                "Gate failed: cheapest supplier quality/compliance below threshold."
            )

    return CostSignal(
        signal=round(signal, 4),
        estimated_savings_usd=round(est_savings, 2),
        spread_pct=round(spread_pct, 2),
        meets_gates=meets_gates,
        best_supplier_id=cheapest.supplier_id if meets_gates else None,
        best_supplier_name=cheapest.supplier_name if meets_gates else None,
        best_supplier_price=cheapest.avg_price if meets_gates else None,
        current_weighted_avg_price=round(weighted_avg, 4) if weighted_avg > 0 else None,
        evidence=evidence,
        missing=missing,
    )


__all__ = [
    "COMPLIANCE_SCORE_THRESHOLD",
    "CostSignal",
    "QUALITY_SCORE_THRESHOLD",
    "SIGNAL_FULL_SPREAD_PCT",
    "SPREAD_PCT_THRESHOLD",
    "SupplierPricing",
    "VOLUME_ADOPTION_FACTOR",
    "build_supplier_pricing",
    "compute_cost_signal",
]
