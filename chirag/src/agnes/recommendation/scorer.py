"""
Phase 7 deterministic scoring.

Pure functions: take signals, Phase 6 acceptability, Phase 4 substitute score,
plus weights/thresholds — return final score and a :class:`RecommendationGrade`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from agnes.models.assessment import RecommendationClass
from agnes.models.recommendation import RecommendationGrade, SourcingSignals


@dataclass(frozen=True)
class SourcingWeights:
    """Weights for the three sourcing signals (should sum to ~1.0)."""

    diversification: float = 0.40
    company_overlap: float = 0.35
    concentration_relief: float = 0.25

    def as_dict(self) -> dict[str, float]:
        return {
            "diversification": self.diversification,
            "company_overlap": self.company_overlap,
            "concentration_relief": self.concentration_relief,
        }


@dataclass(frozen=True)
class FinalScoreConfig:
    """Weights for combining acceptability + substitute score + sourcing + savings.

    ``alpha_savings`` defaults to ``0.0`` so existing deployments — which may
    not yet have procurement data seeded — score identically to Phase 7 v2.
    Operators enabling the cost-savings signal should bump ``alpha_savings``
    and rebalance the other weights so they sum to ``1.0``.
    """

    alpha_acceptability: float = 0.55
    alpha_substitute: float = 0.25
    alpha_sourcing: float = 0.20
    alpha_savings: float = 0.0

    def as_dict(self) -> dict[str, float]:
        return {
            "acceptability": self.alpha_acceptability,
            "substitute": self.alpha_substitute,
            "sourcing": self.alpha_sourcing,
            "savings": self.alpha_savings,
        }


@dataclass(frozen=True)
class GradeThresholds:
    """Final-score cutoffs that map to :class:`RecommendationGrade`."""

    safe: float = 0.70
    reject: float = 0.30

    def as_dict(self) -> dict[str, float]:
        return {"safe": self.safe, "reject": self.reject}


DEFAULT_SOURCING_WEIGHTS: SourcingWeights = SourcingWeights()
DEFAULT_FINAL_WEIGHTS: FinalScoreConfig = FinalScoreConfig()
DEFAULT_THRESHOLDS: GradeThresholds = GradeThresholds()


@dataclass(frozen=True)
class ScoringInputs:
    """Small struct that flows through :func:`map_grade`."""

    acceptability: float
    substitute_score: float | None
    sourcing_benefit: float
    signals: SourcingSignals
    savings_signal: float = 0.0
    has_high_weight_contradiction: bool = False
    contradictions: list[str] = field(default_factory=list)


def _diversification(signals: SourcingSignals) -> float:
    """
    Reward candidates with at least two suppliers.

    Capped at 4 suppliers — we don't want a pathological long-tail catalogue
    to dominate the score.
    """
    n = signals.candidate_supplier_count
    if n <= 1:
        return 0.0
    return min(1.0, (n - 1) / 3.0)


def sourcing_benefit(
    signals: SourcingSignals,
    weights: SourcingWeights = DEFAULT_SOURCING_WEIGHTS,
) -> float:
    """
    Combine the structural signals into a benefit score in ``[0, 1]``.

    When supplier data is missing (``missing_signals=["no_supplier_data"]``),
    returns a neutral ``0.5`` instead of 0 — the candidate isn't penalized for
    sparse inputs; Phase 6 acceptability dominates in that case.
    """
    if "no_supplier_data" in signals.missing_signals:
        return 0.5
    div = _diversification(signals)
    mix = (
        weights.diversification * div
        + weights.company_overlap * signals.company_supplier_overlap
        + weights.concentration_relief * signals.concentration_relief
    )
    return max(0.0, min(1.0, mix))


def final_score(
    acceptability: float,
    substitute_score: float | None,
    sourcing_benefit_value: float,
    cfg: FinalScoreConfig = DEFAULT_FINAL_WEIGHTS,
    *,
    savings_signal: float = 0.0,
) -> float:
    """
    Weighted mix of acceptability, Phase 4 substitute score, sourcing benefit,
    and (optionally) the procurement savings signal.

    ``substitute_score`` may be ``None`` (no Phase 4 row). The missing weight is
    redistributed proportionally across the remaining active components so the
    overall score stays anchored in ``[0, 1]`` regardless of which signals fire.
    """
    acc = max(0.0, min(1.0, acceptability))
    src = max(0.0, min(1.0, sourcing_benefit_value))
    sav = max(0.0, min(1.0, savings_signal))

    active_pairs: list[tuple[float, float]] = [
        (cfg.alpha_acceptability, acc),
        (cfg.alpha_sourcing, src),
        (cfg.alpha_savings, sav),
    ]
    if substitute_score is not None:
        active_pairs.append(
            (cfg.alpha_substitute, max(0.0, min(1.0, substitute_score)))
        )

    total_weight = sum(w for w, _ in active_pairs if w > 0.0)
    if total_weight <= 0.0:
        return 0.0

    weighted = sum(w * v for w, v in active_pairs if w > 0.0)
    return max(0.0, min(1.0, weighted / total_weight))


def map_grade(
    rec_class: RecommendationClass,
    final_score_value: float,
    scoring: ScoringInputs,
    thresholds: GradeThresholds = DEFAULT_THRESHOLDS,
) -> tuple[RecommendationGrade, bool]:
    """
    Map Phase 6 class + final score into a Phase 7 :class:`RecommendationGrade`.

    Returns ``(grade, review_required)``. Phase 6 verdicts veto (``do_not_recommend``
    → ``not_recommended``; ``insufficient_evidence`` → its own grade) regardless of
    how strong the sourcing benefit looks — the numerics shouldn't override the
    reasoning layer.
    """
    if rec_class == "do_not_recommend":
        return "not_recommended", True
    if rec_class == "insufficient_evidence":
        return "potential_substitute_insufficient_evidence", True

    if final_score_value >= thresholds.safe:
        grade: RecommendationGrade = "safe_to_consolidate"
    elif final_score_value <= thresholds.reject:
        grade = "not_recommended"
    else:
        grade = "likely_safe_review_required"

    review_required = grade != "safe_to_consolidate"
    if scoring.has_high_weight_contradiction:
        review_required = True
        if grade == "safe_to_consolidate":
            grade = "likely_safe_review_required"
    return grade, review_required
