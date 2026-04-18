"""Phase 7 Pydantic contract tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from agnes.models.recommendation import (
    ConsolidationOpportunity,
    RecommendationReport,
    SourcingRecommendation,
    SourcingSignals,
)


def _signals(**overrides: object) -> SourcingSignals:
    base = {
        "source_supplier_count": 1,
        "candidate_supplier_count": 2,
        "shared_supplier_ids": [],
        "company_supplier_overlap": 0.25,
        "concentration_relief": 1.0,
        "missing_signals": [],
    }
    base.update(overrides)
    return SourcingSignals(**base)  # type: ignore[arg-type]


def _row(**overrides: object) -> SourcingRecommendation:
    base: dict[str, object] = {
        "company_id": 1,
        "finished_product_id": 10,
        "source_key": "calcium-citrate",
        "candidate_key": "magnesium-citrate",
        "source_display_name": "calcium citrate",
        "candidate_display_name": "magnesium citrate",
        "recommendation_grade": "safe_to_consolidate",
        "final_score": 0.8,
        "acceptability": 0.9,
        "substitute_score": 0.7,
        "sourcing_benefit": 0.6,
        "signals": _signals(),
        "current_suppliers": ["Alpha"],
        "recommended_suppliers": ["Beta", "Gamma"],
        "caveats": [],
        "risk_notes": [],
        "review_required": False,
        "tradeoff_summary": "summary",
        "citations": [],
        "decision_path": "rules",
        "generated_at": datetime.now(UTC),
    }
    base.update(overrides)
    return SourcingRecommendation(**base)  # type: ignore[arg-type]


def test_signals_accept_valid_and_reject_out_of_range() -> None:
    s = _signals(company_supplier_overlap=0.4)
    assert s.company_supplier_overlap == 0.4
    with pytest.raises(ValidationError):
        _signals(company_supplier_overlap=1.2)
    with pytest.raises(ValidationError):
        _signals(concentration_relief=-0.1)


def test_row_key_is_stable() -> None:
    row = _row()
    assert row.row_key() == "1|10|calcium-citrate|magnesium-citrate"


def test_recommendation_is_frozen() -> None:
    row = _row()
    with pytest.raises(ValidationError):
        row.final_score = 0.0  # type: ignore[misc]


def test_recommendation_grade_enum_validation() -> None:
    with pytest.raises(ValidationError):
        _row(recommendation_grade="definitely-not-a-grade")


def test_final_score_bounds() -> None:
    with pytest.raises(ValidationError):
        _row(final_score=1.5)
    with pytest.raises(ValidationError):
        _row(acceptability=-0.1)


def test_opportunity_round_trip() -> None:
    opp = ConsolidationOpportunity(
        source_key="calcium-citrate",
        source_display_name="calcium citrate",
        best_candidate_key="magnesium-citrate",
        best_candidate_display_name="magnesium citrate",
        n_products_covered=2,
        n_companies_covered=1,
        aggregate_final_score=0.7,
        aggregate_sourcing_benefit=0.5,
        recommendation_grade="safe_to_consolidate",
        unique_current_suppliers=["Alpha"],
        unique_recommended_suppliers=["Beta"],
        review_required=False,
        tradeoff_summary="...",
        risk_notes=[],
        top_row_keys=["1|10|calcium-citrate|magnesium-citrate"],
        generated_at=datetime.now(UTC),
    )
    blob = opp.model_dump_json()
    rehydrated = ConsolidationOpportunity.model_validate_json(blob)
    assert rehydrated.source_key == "calcium-citrate"
    assert rehydrated.top_row_keys == opp.top_row_keys


def test_report_round_trip() -> None:
    report = RecommendationReport(
        generated_at=datetime.now(UTC),
        weights={"a": 0.5},
        thresholds={"safe": 0.7, "reject": 0.3},
        n_tuples=0,
        n_opportunities=0,
        n_cache_hits=0,
        n_api_calls=0,
        counts_by_grade={},
        duration_ms=0,
    )
    rehydrated = RecommendationReport.model_validate_json(report.model_dump_json())
    assert rehydrated.schema_version == report.schema_version
