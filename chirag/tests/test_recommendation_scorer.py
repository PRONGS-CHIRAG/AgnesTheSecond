"""Phase 7 scorer unit tests (pure functions)."""

from __future__ import annotations

from agnes.models.recommendation import SourcingSignals
from agnes.recommendation.scorer import (
    DEFAULT_FINAL_WEIGHTS,
    DEFAULT_SOURCING_WEIGHTS,
    DEFAULT_THRESHOLDS,
    ScoringInputs,
    final_score,
    map_grade,
    sourcing_benefit,
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


def test_sourcing_benefit_monotonic_in_diversification() -> None:
    low = sourcing_benefit(_signals(cand=1, overlap=0.0, relief=0.0))
    mid = sourcing_benefit(_signals(cand=2, overlap=0.0, relief=0.0))
    high = sourcing_benefit(_signals(cand=4, overlap=0.0, relief=0.0))
    assert low < mid < high


def test_sourcing_benefit_neutral_when_no_supplier_data() -> None:
    b = sourcing_benefit(_signals(missing=["no_supplier_data"]))
    assert b == 0.5


def test_sourcing_benefit_bounded() -> None:
    b = sourcing_benefit(_signals(cand=100, overlap=1.0, relief=1.0))
    assert 0.0 <= b <= 1.0


def test_final_score_monotonic_in_each_input() -> None:
    base = final_score(0.5, 0.5, 0.5)
    more_accept = final_score(0.9, 0.5, 0.5)
    more_sub = final_score(0.5, 0.9, 0.5)
    more_src = final_score(0.5, 0.5, 0.9)
    assert more_accept > base
    assert more_sub > base
    assert more_src > base


def test_final_score_handles_missing_substitute_score() -> None:
    score = final_score(0.8, None, 0.4)
    assert 0.0 <= score <= 1.0
    alt = final_score(0.8, 0.0, 0.4)
    assert score > alt


def test_map_grade_safe_threshold() -> None:
    scoring = ScoringInputs(
        acceptability=0.9,
        substitute_score=0.9,
        sourcing_benefit=0.8,
        signals=_signals(),
    )
    grade, review = map_grade("recommend", 0.85, scoring, DEFAULT_THRESHOLDS)
    assert grade == "safe_to_consolidate"
    assert review is False


def test_map_grade_reject_threshold() -> None:
    scoring = ScoringInputs(
        acceptability=0.1,
        substitute_score=0.1,
        sourcing_benefit=0.1,
        signals=_signals(src=5, cand=1),
    )
    grade, review = map_grade("recommend_with_caveats", 0.2, scoring, DEFAULT_THRESHOLDS)
    assert grade == "not_recommended"
    assert review is True


def test_phase6_veto_do_not_recommend_overrides_score() -> None:
    scoring = ScoringInputs(
        acceptability=0.9,
        substitute_score=0.9,
        sourcing_benefit=0.9,
        signals=_signals(),
    )
    grade, review = map_grade("do_not_recommend", 0.95, scoring, DEFAULT_THRESHOLDS)
    assert grade == "not_recommended"
    assert review is True


def test_phase6_veto_insufficient_evidence_overrides_score() -> None:
    scoring = ScoringInputs(
        acceptability=0.9,
        substitute_score=0.9,
        sourcing_benefit=0.9,
        signals=_signals(),
    )
    grade, review = map_grade(
        "insufficient_evidence", 0.95, scoring, DEFAULT_THRESHOLDS
    )
    assert grade == "potential_substitute_insufficient_evidence"
    assert review is True


def test_high_weight_contradiction_downgrades_safe() -> None:
    scoring = ScoringInputs(
        acceptability=0.9,
        substitute_score=0.9,
        sourcing_benefit=0.9,
        signals=_signals(),
        has_high_weight_contradiction=True,
        contradictions=["regulatory"],
    )
    grade, review = map_grade("recommend", 0.95, scoring, DEFAULT_THRESHOLDS)
    assert grade == "likely_safe_review_required"
    assert review is True


def test_defaults_sum_to_one() -> None:
    assert (
        DEFAULT_SOURCING_WEIGHTS.diversification
        + DEFAULT_SOURCING_WEIGHTS.company_overlap
        + DEFAULT_SOURCING_WEIGHTS.concentration_relief
    ) == 1.0
    assert (
        DEFAULT_FINAL_WEIGHTS.alpha_acceptability
        + DEFAULT_FINAL_WEIGHTS.alpha_substitute
        + DEFAULT_FINAL_WEIGHTS.alpha_sourcing
    ) == 1.0
