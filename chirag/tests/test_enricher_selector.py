"""Tests for Phase 5 ``select_pairs``."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from agnes.evidence.enricher import select_pairs
from agnes.models.substitutes import (
    SUBSTITUTES_SCHEMA_VERSION,
    CandidateFeatures,
    SubstituteCandidate,
    SubstituteCandidateReport,
)


def _features() -> CandidateFeatures:
    return CandidateFeatures(
        family_match=True,
        role_match=True,
        lexical_sim=0.3,
        embed_sim=0.8,
        supplier_overlap=0.5,
        co_company_overlap=0.2,
        missing_signals=[],
    )


def _cand(source: str, candidate: str, score: float) -> SubstituteCandidate:
    return SubstituteCandidate(
        source_key=source,
        candidate_key=candidate,
        family="vitamin_mineral",
        roles=["active_ingredient"],
        score=score,
        features=_features(),
        embedding_model="stub-embed",
        taxonomy_version="v1",
        graph_schema_version="v1",
        schema_version=SUBSTITUTES_SCHEMA_VERSION,
    )


def _report(cands: list[SubstituteCandidate]) -> SubstituteCandidateReport:
    return SubstituteCandidateReport(
        taxonomy_version="v1",
        graph_schema_version="v1",
        generated_at=datetime.now(UTC),
        embedding_model="stub-embed",
        weights={
            "family": 0.3,
            "role": 0.15,
            "embed": 0.35,
            "lexical": 0.1,
            "supplier_overlap": 0.1,
        },
        min_score=0.0,
        top_k=10,
        cross_family=False,
        n_targets=len({c.source_key for c in cands}),
        n_with_candidates=len({c.source_key for c in cands}),
        n_without_candidates=0,
        duration_ms=1,
        candidates=cands,
    )


def test_select_pairs_orders_by_best_score_desc() -> None:
    report = _report(
        [
            _cand("a", "a1", 0.4),
            _cand("a", "a2", 0.35),
            _cand("b", "b1", 0.9),
            _cand("b", "b2", 0.85),
            _cand("c", "c1", 0.6),
        ]
    )
    pairs = select_pairs(report, top_sources=2, per_source=2)
    assert pairs == [("b", "b1"), ("b", "b2"), ("c", "c1")]


def test_select_pairs_respects_per_source_truncation() -> None:
    report = _report(
        [
            _cand("x", "x1", 0.9),
            _cand("x", "x2", 0.85),
            _cand("x", "x3", 0.8),
        ]
    )
    pairs = select_pairs(report, top_sources=5, per_source=2)
    assert pairs == [("x", "x1"), ("x", "x2")]


def test_select_pairs_source_filter() -> None:
    report = _report(
        [
            _cand("a", "a1", 0.4),
            _cand("b", "b1", 0.9),
        ]
    )
    pairs = select_pairs(report, top_sources=5, per_source=5, source_filter="a")
    assert pairs == [("a", "a1")]


def test_select_pairs_source_filter_missing_returns_empty() -> None:
    report = _report([_cand("a", "a1", 0.4)])
    assert select_pairs(report, top_sources=5, per_source=5, source_filter="zzz") == []


def test_select_pairs_negative_raises() -> None:
    report = _report([_cand("a", "a1", 0.4)])
    with pytest.raises(ValueError):
        select_pairs(report, top_sources=-1, per_source=1)


def test_select_pairs_tie_break_by_source_key() -> None:
    report = _report(
        [
            _cand("b", "b1", 0.5),
            _cand("a", "a1", 0.5),
        ]
    )
    pairs = select_pairs(report, top_sources=2, per_source=1)
    assert pairs == [("a", "a1"), ("b", "b1")]
