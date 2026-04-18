"""
Phase 7 deterministic scoring — Prioritization Framework (v3).

Explicit tension balancing between consolidation leverage and concentration risk.
Five dimensions combine into ``final_score``; the scorer is pure (no I/O, no LLM)
so the numerics are reproducible and unit-testable.

Dimensions
----------

* ``consolidation_benefit`` (0.35) — volume leverage: how much of the candidate
  is already purchased by this company's suppliers, plus relief from single-source
  pressure on the incumbent.
* ``evidence_confidence`` (0.25) — Phase 6 acceptability, which already embeds
  Phase 5 grounding and claim polarity.
* ``compliance_fit``  (0.20) — regulatory + certification + functional safety,
  penalized by high-weight contradictions.
* ``supplier_diversification`` (0.10) — **penalty** when consolidation leaves a
  single supplier; the key position differentiating this framework from naive
  minimization.
* ``switching_feasibility`` (0.10) — how actionable the swap is, given the
  company's existing supplier relationships.

The scorer also emits a ``concentration_risk_downgrade`` flag whenever
``supplier_diversification`` falls below the configured floor *and* the weighted
score would otherwise yield ``safe_to_consolidate``; in that case the grade is
knocked down to ``likely_safe_review_required`` and ``review_required`` is set.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from agnes.models.assessment import RecommendationClass
from agnes.models.recommendation import (
    DimensionScores,
    RecommendationGrade,
    SourcingSignals,
)

HIGH_WEIGHT_CONTRADICTION_KEYS = frozenset(
    {"functional_equivalence", "regulatory", "certification"}
)


@dataclass(frozen=True)
class PrioritizationWeights:
    """Weights for the 5 prioritization dimensions — sum should be ~1.0."""

    consolidation_benefit: float = 0.35
    evidence_confidence: float = 0.25
    compliance_fit: float = 0.20
    supplier_diversification: float = 0.10
    switching_feasibility: float = 0.10

    def as_dict(self) -> dict[str, float]:
        return {
            "consolidation_benefit": self.consolidation_benefit,
            "evidence_confidence": self.evidence_confidence,
            "compliance_fit": self.compliance_fit,
            "supplier_diversification": self.supplier_diversification,
            "switching_feasibility": self.switching_feasibility,
        }


@dataclass(frozen=True)
class GradeThresholds:
    """Final-score cutoffs that map to :class:`RecommendationGrade`.

    ``diversification_floor`` is the load-bearing guard: when
    ``supplier_diversification`` is below this, a ``safe_to_consolidate`` grade
    is downgraded to ``likely_safe_review_required``.
    """

    safe: float = 0.70
    reject: float = 0.30
    diversification_floor: float = 0.30

    def as_dict(self) -> dict[str, float]:
        return {
            "safe": self.safe,
            "reject": self.reject,
            "diversification_floor": self.diversification_floor,
        }


DEFAULT_WEIGHTS: PrioritizationWeights = PrioritizationWeights()
DEFAULT_THRESHOLDS: GradeThresholds = GradeThresholds()


@dataclass(frozen=True)
class ScoringInputs:
    """Struct used by :func:`map_grade` and the tradeoff-summary builder."""

    acceptability: float
    substitute_score: float | None
    dimensions: DimensionScores
    signals: SourcingSignals
    has_high_weight_contradiction: bool = False
    contradictions: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# per-dimension signals
# ---------------------------------------------------------------------------


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def consolidation_benefit_score(signals: SourcingSignals) -> float:
    """Combine company-level overlap with concentration relief.

    ``company_supplier_overlap`` rewards candidates whose suppliers already
    serve this company (existing leverage). ``concentration_relief`` rewards
    candidates that break a single-supplier lock on the incumbent raw. When
    supplier data is missing we return a neutral ``0.5`` so the dimension
    doesn't unfairly punish sparse-DB cases — Phase 6 acceptability carries
    the decision.
    """
    if "no_supplier_data" in signals.missing_signals:
        return 0.5
    return _clamp(
        0.5 * signals.company_supplier_overlap + 0.5 * signals.concentration_relief
    )


def evidence_confidence_score(acceptability: float) -> float:
    """Phase 6 ``acceptability`` already embeds grounding strength + polarity.

    Passing it through keeps the provenance chain explicit: the confidence we
    report here is the same scalar Phase 6 wrote on the assessment row, so the
    UI can show them side by side without reconciliation.
    """
    return _clamp(acceptability)


def compliance_fit_score(
    rec_class: RecommendationClass,
    contradictions: list[str],
) -> float:
    """Regulatory / certification / functional-equivalence safety.

    Rules:

    * ``do_not_recommend`` → 0.0 (the Phase 6 veto is absolute).
    * ``insufficient_evidence`` → 0.5 (neutral; we can't prove safety either way).
    * Otherwise start at 1.0 and subtract 0.5 per high-weight contradiction
      (functional_equivalence, regulatory, certification), flooring at 0.0.
    """
    if rec_class == "do_not_recommend":
        return 0.0
    if rec_class == "insufficient_evidence":
        return 0.5
    high_weight_hits = sum(
        1 for k in contradictions if k in HIGH_WEIGHT_CONTRADICTION_KEYS
    )
    return _clamp(1.0 - 0.5 * high_weight_hits)


def supplier_diversification_score(signals: SourcingSignals) -> float:
    """Penalize monopoly risk after consolidation.

    Approximates the post-consolidation supplier count with
    ``candidate_supplier_count`` — the company inherits the candidate's sourcing.

    * 0 suppliers (no data) → 0.5 neutral (Phase 6 dominates).
    * 1 supplier → 0.0 (single-source monopoly; the load-bearing penalty).
    * 2 suppliers → 0.5 (barely diversified).
    * 3+ suppliers → 1.0 (well-diversified).
    """
    n = signals.candidate_supplier_count
    if n == 0:
        return 0.5 if "no_supplier_data" in signals.missing_signals else 0.0
    if n == 1:
        return 0.0
    return _clamp((n - 1) / 2.0)


def switching_feasibility_score(signals: SourcingSignals) -> float:
    """How actionable the swap is today.

    Baseline of 0.4 — onboarding a new supplier is always possible but not free.
    The remaining 0.6 is gated by ``company_supplier_overlap``: candidates
    already supplying this company for some raw are much closer to ready.
    Missing data → neutral 0.5.
    """
    if "no_supplier_data" in signals.missing_signals:
        return 0.5
    return _clamp(0.4 + 0.6 * signals.company_supplier_overlap)


def compute_dimension_scores(
    signals: SourcingSignals,
    *,
    acceptability: float,
    rec_class: RecommendationClass,
    contradictions: list[str],
) -> DimensionScores:
    """Build a :class:`DimensionScores` from Phase 6 + structural signals."""
    return DimensionScores(
        consolidation_benefit=round(consolidation_benefit_score(signals), 4),
        evidence_confidence=round(evidence_confidence_score(acceptability), 4),
        compliance_fit=round(compliance_fit_score(rec_class, contradictions), 4),
        supplier_diversification=round(supplier_diversification_score(signals), 4),
        switching_feasibility=round(switching_feasibility_score(signals), 4),
    )


# ---------------------------------------------------------------------------
# combination
# ---------------------------------------------------------------------------


def prioritization_final_score(
    dims: DimensionScores,
    weights: PrioritizationWeights = DEFAULT_WEIGHTS,
) -> float:
    """Weighted sum of the 5 dimensions, clamped to ``[0, 1]``."""
    value = (
        weights.consolidation_benefit * dims.consolidation_benefit
        + weights.evidence_confidence * dims.evidence_confidence
        + weights.compliance_fit * dims.compliance_fit
        + weights.supplier_diversification * dims.supplier_diversification
        + weights.switching_feasibility * dims.switching_feasibility
    )
    return _clamp(value)


def sourcing_benefit_from_dimensions(dims: DimensionScores) -> float:
    """Backward-compat surface: a single structural-sourcing scalar in ``[0, 1]``.

    Exposed so the existing ``SourcingRecommendation.sourcing_benefit`` field
    retains a meaningful value for the deterministic tradeoff summary and any
    downstream consumer that hasn't upgraded to dimension_scores yet.
    """
    return _clamp(
        (dims.consolidation_benefit + dims.supplier_diversification) / 2.0
    )


# ---------------------------------------------------------------------------
# grade mapping
# ---------------------------------------------------------------------------


def map_grade(
    rec_class: RecommendationClass,
    final_score_value: float,
    scoring: ScoringInputs,
    thresholds: GradeThresholds = DEFAULT_THRESHOLDS,
) -> tuple[RecommendationGrade, bool, bool]:
    """Map Phase 6 class + final score + dimensions into a Phase 7 grade.

    Returns ``(grade, review_required, concentration_risk_downgrade)``.

    Veto order:

    1. Phase 6 ``do_not_recommend`` → ``not_recommended`` (absolute).
    2. Phase 6 ``insufficient_evidence`` → its own grade.
    3. ``concentration_risk_downgrade`` — when ``supplier_diversification``
       is below the configured floor and the weighted score would otherwise
       clear the ``safe`` threshold, grade is capped at
       ``likely_safe_review_required``. This is the literal implementation
       of the "we don't optimize for fewer suppliers" position.
    4. High-weight contradictions downgrade from safe → review_required.
    """
    if rec_class == "do_not_recommend":
        return "not_recommended", True, False
    if rec_class == "insufficient_evidence":
        return "potential_substitute_insufficient_evidence", True, False

    if final_score_value >= thresholds.safe:
        grade: RecommendationGrade = "safe_to_consolidate"
    elif final_score_value <= thresholds.reject:
        grade = "not_recommended"
    else:
        grade = "likely_safe_review_required"

    review_required = grade != "safe_to_consolidate"
    concentration_downgrade = False

    if (
        grade == "safe_to_consolidate"
        and scoring.dimensions.supplier_diversification < thresholds.diversification_floor
    ):
        grade = "likely_safe_review_required"
        review_required = True
        concentration_downgrade = True

    if scoring.has_high_weight_contradiction:
        review_required = True
        if grade == "safe_to_consolidate":
            grade = "likely_safe_review_required"

    return grade, review_required, concentration_downgrade
