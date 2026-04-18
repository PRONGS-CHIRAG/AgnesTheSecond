"""Schema round-trips + enum validation for Phase 6 models."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from agnes.models.assessment import (
    ASSESSMENT_SCHEMA_VERSION,
    AssessmentContext,
    AssessmentReport,
    SubstituteAssessment,
    SubstituteAssessmentLLM,
)
from agnes.models.evidence import CitationRef


def _citation() -> CitationRef:
    return CitationRef(
        url="https://example.com/spec",
        title="Spec",
        domain="example.com",
        retrieved_at=datetime(2026, 4, 18, tzinfo=UTC),
    )


def test_substitute_assessment_round_trip() -> None:
    a = SubstituteAssessment(
        company_id=1,
        company_name="Acme",
        finished_product_id=10,
        finished_product_sku="ACME-10",
        source_key="calcium-citrate",
        candidate_key="magnesium-citrate",
        source_display_name="calcium citrate",
        candidate_display_name="magnesium citrate",
        recommendation_class="recommend_with_caveats",
        acceptability=0.62,
        missing_information=["certification"],
        contradictions=["regulatory"],
        caveats=["pilot scale only"],
        rationale="borderline but plausible",
        decision_path="rules",
        citations_used=[_citation()],
        substitute_score=0.78,
        generated_at=datetime.now(UTC),
        llm_model=None,
    )
    round_tripped = SubstituteAssessment.model_validate_json(a.model_dump_json())
    assert round_tripped == a
    assert round_tripped.schema_version == ASSESSMENT_SCHEMA_VERSION


def test_substitute_assessment_rejects_bad_enum() -> None:
    with pytest.raises(ValidationError):
        SubstituteAssessment(
            company_id=1,
            finished_product_id=1,
            source_key="a",
            candidate_key="b",
            source_display_name="a",
            candidate_display_name="b",
            recommendation_class="maybe",  # type: ignore[arg-type]
            acceptability=0.5,
            rationale="x",
            decision_path="rules",
            generated_at=datetime.now(UTC),
        )


def test_substitute_assessment_acceptability_bounds() -> None:
    with pytest.raises(ValidationError):
        SubstituteAssessment(
            company_id=1,
            finished_product_id=1,
            source_key="a",
            candidate_key="b",
            source_display_name="a",
            candidate_display_name="b",
            recommendation_class="recommend",
            acceptability=1.5,
            rationale="x",
            decision_path="rules",
            generated_at=datetime.now(UTC),
        )


def test_substitute_assessment_llm_round_trip() -> None:
    out = SubstituteAssessmentLLM(
        recommendation_class="do_not_recommend",
        rationale="allergen risk",
        caveats=["requires regulatory review"],
        missing_information=["regulatory", "certification"],
    )
    json_text = out.model_dump_json()
    parsed = SubstituteAssessmentLLM.model_validate_json(json_text)
    assert parsed == out


def test_assessment_context_frozen() -> None:
    ctx = AssessmentContext(
        company_id=1,
        finished_product_id=1,
        source_key="a",
        candidate_key="b",
        source_display_name="a",
        candidate_display_name="b",
    )
    with pytest.raises(ValidationError):
        ctx.company_id = 999  # type: ignore[misc]


def test_assessment_report_counts_by_class_optional() -> None:
    now = datetime.now(UTC)
    rep = AssessmentReport(
        generated_at=now,
        llm_model=None,
        weights={"functional_equivalence": 0.35},
        thresholds={"accept": 0.75, "reject": 0.35, "min_grounded_claims": 2.0},
        n_tuples=0,
        n_rules_decisions=0,
        n_llm_decisions=0,
        n_cache_hits=0,
        n_api_calls=0,
        duration_ms=0,
    )
    assert rep.counts_by_class == {}
    assert rep.partial is False
