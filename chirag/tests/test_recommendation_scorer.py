"""Phase 7 scorer unit tests — 5-dimension Prioritization Framework."""

from __future__ import annotations

import pytest

from agnes.models.recommendation import DimensionScores, SourcingSignals
from agnes.recommendation.scorer import (
    DEFAULT_THRESHOLDS,
    DEFAULT_WEIGHTS,
    ScoringInputs,
    compliance_fit_score,
    compute_dimension_scores,
    consolidation_benefit_score,
    evidence_confidence_score,
    map_grade,
    prioritization_final_score,
    sourcing_benefit_from_dimensions,
    supplier_diversification_score,
    switching_feasibility_score,
)


def _signals(
    *,
    src: int = 1,
    cand: int = 3,
    overlap: float = 0.5,
    relief: float = 1.0,
    missing: list[str] | None = None,
) -> SourcingSignals:
    return SourcingSignals(
        source_supplier_count=src,
        candidate_supplier_count=cand,
        shared_supplier_ids=[],
        company_supplier_overlap=overlap,
        concentration_relief=relief,
        missing_signals=missing or [],
    )


def _dims(**overrides: float) -> DimensionScores:
    base = {
        "consolidation_benefit": 0.5,
        "evidence_confidence": 0.5,
        "compliance_fit": 0.5,
        "supplier_diversification": 0.5,
        "switching_feasibility": 0.5,
    }
    base.update(overrides)
    return DimensionScores(**base)


# ---------------------------------------------------------------------------
# per-dimension signals
# ---------------------------------------------------------------------------


def test_consolidation_benefit_blends_overlap_and_relief() -> None:
    s = _signals(overlap=0.0, relief=0.0, cand=3)
    assert consolidation_benefit_score(s) == 0.0
    s = _signals(overlap=1.0, relief=1.0, cand=3)
    assert consolidation_benefit_score(s) == 1.0
    s = _signals(overlap=0.4, relief=0.8, cand=3)
    assert consolidation_benefit_score(s) == pytest.approx(0.6)


def test_consolidation_benefit_neutral_when_missing_data() -> None:
    s = _signals(missing=["no_supplier_data"])
    assert consolidation_benefit_score(s) == 0.5


def test_evidence_confidence_passes_through_acceptability() -> None:
    assert evidence_confidence_score(0.0) == 0.0
    assert evidence_confidence_score(0.7) == 0.7
    assert evidence_confidence_score(1.2) == 1.0


def test_compliance_fit_vetos_on_do_not_recommend() -> None:
    assert compliance_fit_score("do_not_recommend", []) == 0.0


def test_compliance_fit_neutral_on_insufficient_evidence() -> None:
    assert compliance_fit_score("insufficient_evidence", []) == 0.5


def test_compliance_fit_penalizes_high_weight_contradictions() -> None:
    assert compliance_fit_score("recommend", []) == 1.0
    assert compliance_fit_score("recommend", ["regulatory"]) == 0.5
    assert compliance_fit_score("recommend", ["regulatory", "certification"]) == 0.0
    # low-weight contradictions do not affect the score
    assert compliance_fit_score("recommend", ["price_availability"]) == 1.0


def test_supplier_diversification_penalizes_monopoly() -> None:
    assert supplier_diversification_score(_signals(cand=1)) == 0.0
    assert supplier_diversification_score(_signals(cand=2)) == 0.5
    assert supplier_diversification_score(_signals(cand=3)) == 1.0
    assert supplier_diversification_score(_signals(cand=10)) == 1.0
    assert (
        supplier_diversification_score(_signals(cand=0, missing=["no_supplier_data"]))
        == 0.5
    )


def test_switching_feasibility_rewards_existing_relationships() -> None:
    assert switching_feasibility_score(_signals(overlap=0.0, cand=3)) == 0.4
    assert switching_feasibility_score(_signals(overlap=1.0, cand=3)) == 1.0
    assert switching_feasibility_score(_signals(missing=["no_supplier_data"])) == 0.5


# ---------------------------------------------------------------------------
# combination
# ---------------------------------------------------------------------------


def test_prioritization_final_score_weighted_sum() -> None:
    dims = _dims(
        consolidation_benefit=1.0,
        evidence_confidence=0.0,
        compliance_fit=0.0,
        supplier_diversification=0.0,
        switching_feasibility=0.0,
    )
    assert (
        prioritization_final_score(dims, DEFAULT_WEIGHTS)
        == DEFAULT_WEIGHTS.consolidation_benefit
    )

    all_one = _dims(
        consolidation_benefit=1.0,
        evidence_confidence=1.0,
        compliance_fit=1.0,
        supplier_diversification=1.0,
        switching_feasibility=1.0,
    )
    assert prioritization_final_score(all_one) == 1.0

    all_zero = _dims(
        consolidation_benefit=0.0,
        evidence_confidence=0.0,
        compliance_fit=0.0,
        supplier_diversification=0.0,
        switching_feasibility=0.0,
    )
    assert prioritization_final_score(all_zero) == 0.0


def test_defaults_sum_to_one() -> None:
    total = (
        DEFAULT_WEIGHTS.consolidation_benefit
        + DEFAULT_WEIGHTS.evidence_confidence
        + DEFAULT_WEIGHTS.compliance_fit
        + DEFAULT_WEIGHTS.supplier_diversification
        + DEFAULT_WEIGHTS.switching_feasibility
    )
    assert abs(total - 1.0) < 1e-9


def test_compute_dimension_scores_wires_inputs() -> None:
    signals = _signals(cand=3, overlap=0.6, relief=1.0)
    dims = compute_dimension_scores(
        signals,
        acceptability=0.8,
        rec_class="recommend",
        contradictions=[],
    )
    assert dims.evidence_confidence == 0.8
    assert dims.supplier_diversification == 1.0
    assert dims.compliance_fit == 1.0
    assert 0.0 <= dims.consolidation_benefit <= 1.0


def test_sourcing_benefit_backward_compat() -> None:
    dims = _dims(consolidation_benefit=0.8, supplier_diversification=0.2)
    assert sourcing_benefit_from_dimensions(dims) == 0.5


# ---------------------------------------------------------------------------
# grade mapping
# ---------------------------------------------------------------------------


def test_map_grade_safe_when_all_signals_high() -> None:
    dims = _dims(
        consolidation_benefit=0.9,
        evidence_confidence=0.9,
        compliance_fit=0.9,
        supplier_diversification=0.9,
        switching_feasibility=0.9,
    )
    scoring = ScoringInputs(
        acceptability=0.9,
        substitute_score=0.9,
        dimensions=dims,
        signals=_signals(cand=3),
    )
    grade, review, downgrade = map_grade("recommend", 0.9, scoring, DEFAULT_THRESHOLDS)
    assert grade == "safe_to_consolidate"
    assert review is False
    assert downgrade is False


def test_monopoly_downgrade_blocks_safe_to_consolidate() -> None:
    dims = _dims(
        consolidation_benefit=0.9,
        evidence_confidence=0.9,
        compliance_fit=0.9,
        supplier_diversification=0.0,
        switching_feasibility=0.9,
    )
    scoring = ScoringInputs(
        acceptability=0.9,
        substitute_score=0.9,
        dimensions=dims,
        signals=_signals(cand=1),
    )
    grade, review, downgrade = map_grade("recommend", 0.85, scoring, DEFAULT_THRESHOLDS)
    assert grade == "likely_safe_review_required"
    assert review is True
    assert downgrade is True


def test_monopoly_downgrade_does_not_affect_already_review_grade() -> None:
    dims = _dims(supplier_diversification=0.0)
    scoring = ScoringInputs(
        acceptability=0.5,
        substitute_score=0.5,
        dimensions=dims,
        signals=_signals(cand=1),
    )
    grade, review, downgrade = map_grade("recommend", 0.55, scoring, DEFAULT_THRESHOLDS)
    assert grade == "likely_safe_review_required"
    assert downgrade is False  # not a downgrade from safe


def test_phase6_veto_do_not_recommend() -> None:
    dims = _dims()
    scoring = ScoringInputs(
        acceptability=0.9,
        substitute_score=0.9,
        dimensions=dims,
        signals=_signals(cand=3),
    )
    grade, review, downgrade = map_grade("do_not_recommend", 0.95, scoring)
    assert grade == "not_recommended"
    assert review is True
    assert downgrade is False


def test_phase6_veto_insufficient_evidence() -> None:
    dims = _dims()
    scoring = ScoringInputs(
        acceptability=0.9,
        substitute_score=0.9,
        dimensions=dims,
        signals=_signals(cand=3),
    )
    grade, review, downgrade = map_grade("insufficient_evidence", 0.95, scoring)
    assert grade == "potential_substitute_insufficient_evidence"
    assert review is True
    assert downgrade is False


def test_high_weight_contradiction_downgrades_safe() -> None:
    dims = _dims(supplier_diversification=0.9)
    scoring = ScoringInputs(
        acceptability=0.9,
        substitute_score=0.9,
        dimensions=dims,
        signals=_signals(cand=3),
        has_high_weight_contradiction=True,
        contradictions=["regulatory"],
    )
    grade, review, downgrade = map_grade("recommend", 0.95, scoring)
    assert grade == "likely_safe_review_required"
    assert review is True
    assert downgrade is False


def test_reject_threshold_maps_not_recommended() -> None:
    dims = _dims(
        consolidation_benefit=0.1,
        evidence_confidence=0.1,
        compliance_fit=0.1,
        supplier_diversification=0.1,
        switching_feasibility=0.1,
    )
    scoring = ScoringInputs(
        acceptability=0.1,
        substitute_score=0.1,
        dimensions=dims,
        signals=_signals(cand=1),
    )
    grade, review, downgrade = map_grade("recommend", 0.15, scoring)
    assert grade == "not_recommended"
    assert review is True
