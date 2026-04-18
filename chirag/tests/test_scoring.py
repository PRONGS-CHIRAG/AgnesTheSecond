"""Unit tests for Phase 4 scoring."""

from __future__ import annotations

from agnes.models.substitutes import CandidateFeatures
from agnes.substitutes.scoring import (
    DEFAULT_WEIGHTS,
    MISSING_SIGNAL_PENALTY,
    normalize_weights,
    score_candidate,
)


def _features(**overrides) -> CandidateFeatures:
    base = {
        "family_match": True,
        "role_match": True,
        "lexical_sim": 0.5,
        "embed_sim": 0.8,
        "supplier_overlap": 0.25,
        "co_company_overlap": 0.0,
        "missing_signals": [],
    }
    base.update(overrides)
    return CandidateFeatures(**base)


def test_normalize_weights_fills_defaults() -> None:
    w = normalize_weights({"family": 0.5})
    assert w["family"] == 0.5
    for k in DEFAULT_WEIGHTS:
        assert k in w


def test_score_candidate_orders_by_signal_strength() -> None:
    strong = _features()
    weak = _features(family_match=False, role_match=False, embed_sim=0.1, lexical_sim=0.0)
    assert score_candidate(strong) > score_candidate(weak)


def test_score_candidate_missing_signal_penalty() -> None:
    base = _features()
    penalized = _features(embed_sim=None, missing_signals=["embed"])
    diff = score_candidate(base) - score_candidate(penalized)
    # Lost embed weight contribution (0.35 * 0.8 = 0.28) + 0.05 missing penalty
    expected_drop = DEFAULT_WEIGHTS["embed"] * 0.8 + MISSING_SIGNAL_PENALTY
    assert abs(diff - expected_drop) < 1e-9


def test_score_candidate_clamped_to_unit_interval() -> None:
    inflated = _features(lexical_sim=1.0, embed_sim=1.0, supplier_overlap=1.0)
    s = score_candidate(inflated, {"family": 10.0, "role": 10.0})
    assert 0.0 <= s <= 1.0
