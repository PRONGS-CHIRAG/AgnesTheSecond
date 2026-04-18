"""Phase 7 builder tests: row composition + rollup semantics."""

from __future__ import annotations

import random
from datetime import UTC, datetime

from agnes.models.assessment import SubstituteAssessment
from agnes.models.evidence import CitationRef
from agnes.recommendation.builder import build_rows, rollup_opportunities
from agnes.recommendation.scorer import (
    DEFAULT_FINAL_WEIGHTS,
    DEFAULT_SOURCING_WEIGHTS,
    DEFAULT_THRESHOLDS,
)
from agnes.recommendation.signals import SupplierIndex


def _index(
    *,
    suppliers_by_key: dict[str, set[int]] | None = None,
    names_by_key: dict[str, list[str]] | None = None,
    company: dict[int, set[int]] | None = None,
) -> SupplierIndex:
    return SupplierIndex(
        suppliers_by_key=suppliers_by_key or {},
        supplier_names_by_key=names_by_key or {},
        suppliers_by_company=company or {},
        raw_ids_by_key={},
    )


def _assessment(
    *,
    company_id: int,
    product_id: int,
    source_key: str,
    candidate_key: str,
    rec_class: str = "recommend",
    acceptability: float = 0.9,
    decision_path: str = "rules",
    citations: list[CitationRef] | None = None,
    caveats: list[str] | None = None,
    contradictions: list[str] | None = None,
) -> SubstituteAssessment:
    return SubstituteAssessment(
        company_id=company_id,
        company_name=f"Co-{company_id}",
        finished_product_id=product_id,
        finished_product_sku=f"SKU-{product_id}",
        source_key=source_key,
        candidate_key=candidate_key,
        source_display_name=source_key.replace("-", " "),
        candidate_display_name=candidate_key.replace("-", " "),
        recommendation_class=rec_class,  # type: ignore[arg-type]
        acceptability=acceptability,
        missing_information=[],
        contradictions=contradictions or [],  # type: ignore[arg-type]
        caveats=caveats or [],
        rationale="rules-rationale",
        decision_path=decision_path,  # type: ignore[arg-type]
        citations_used=citations or [],
        substitute_score=0.7,
        generated_at=datetime.now(UTC),
        llm_model=None,
    )


def _cite() -> CitationRef:
    return CitationRef(
        url="https://example.com/a",
        title="A",
        domain="example.com",
        retrieved_at=datetime(2026, 4, 18, tzinfo=UTC),
    )


def test_build_rows_passes_through_citations_and_caveats() -> None:
    cite = _cite()
    assessment = _assessment(
        company_id=1,
        product_id=10,
        source_key="calcium-citrate",
        candidate_key="magnesium-citrate",
        citations=[cite],
        caveats=["requires review"],
    )
    index = _index(
        suppliers_by_key={
            "calcium-citrate": {1},
            "magnesium-citrate": {2, 3},
        },
        names_by_key={
            "calcium-citrate": ["Alpha"],
            "magnesium-citrate": ["Beta", "Gamma"],
        },
        company={1: set()},
    )
    rows = build_rows(
        [assessment],
        supplier_index=index,
        candidates_report=None,
        sourcing_weights=DEFAULT_SOURCING_WEIGHTS,
        final_cfg=DEFAULT_FINAL_WEIGHTS,
        thresholds=DEFAULT_THRESHOLDS,
    )
    assert len(rows) == 1
    row = rows[0]
    assert row.citations == [cite]
    assert row.caveats == ["requires review"]
    assert row.current_suppliers == ["Alpha"]
    assert row.recommended_suppliers == ["Beta", "Gamma"]
    assert row.signals.concentration_relief == 1.0


def test_build_rows_applies_phase6_veto() -> None:
    assessment = _assessment(
        company_id=1,
        product_id=10,
        source_key="s",
        candidate_key="c",
        rec_class="do_not_recommend",
        acceptability=0.1,
    )
    rows = build_rows(
        [assessment],
        supplier_index=_index(),
        candidates_report=None,
        sourcing_weights=DEFAULT_SOURCING_WEIGHTS,
        final_cfg=DEFAULT_FINAL_WEIGHTS,
        thresholds=DEFAULT_THRESHOLDS,
    )
    assert rows[0].recommendation_grade == "not_recommended"
    assert rows[0].review_required is True


def test_rollup_picks_best_candidate_per_source() -> None:
    index = _index(
        suppliers_by_key={
            "s": {1},
            "strong": {2, 3},
            "weak": {4},
        },
        names_by_key={
            "s": ["Incumbent"],
            "strong": ["Alpha", "Beta"],
            "weak": ["Gamma"],
        },
        company={1: set(), 2: {2}},
    )
    assessments = [
        _assessment(
            company_id=1, product_id=10, source_key="s", candidate_key="strong",
            acceptability=0.9,
        ),
        _assessment(
            company_id=2, product_id=11, source_key="s", candidate_key="strong",
            acceptability=0.85,
        ),
        _assessment(
            company_id=1, product_id=10, source_key="s", candidate_key="weak",
            acceptability=0.4,
        ),
    ]
    rows = build_rows(
        assessments,
        supplier_index=index,
        candidates_report=None,
        sourcing_weights=DEFAULT_SOURCING_WEIGHTS,
        final_cfg=DEFAULT_FINAL_WEIGHTS,
        thresholds=DEFAULT_THRESHOLDS,
    )
    opportunities = rollup_opportunities(rows)
    assert len(opportunities) == 1
    opp = opportunities[0]
    assert opp.best_candidate_key == "strong"
    assert opp.n_products_covered == 2
    assert opp.n_companies_covered == 2
    assert set(opp.unique_recommended_suppliers) == {"Alpha", "Beta"}
    assert opp.unique_current_suppliers == ["Incumbent"]


def test_rollup_is_stable_under_row_shuffling() -> None:
    index = _index(
        suppliers_by_key={
            "s": {1},
            "a": {2, 3},
            "b": {4},
        },
        names_by_key={"s": ["X"], "a": ["Y"], "b": ["Z"]},
        company={1: set()},
    )
    assessments = [
        _assessment(
            company_id=1, product_id=p, source_key="s", candidate_key=cand,
            acceptability=acc,
        )
        for (p, cand, acc) in [
            (10, "a", 0.9),
            (11, "a", 0.85),
            (10, "b", 0.4),
        ]
    ]
    rows1 = build_rows(
        assessments,
        supplier_index=index,
        candidates_report=None,
        sourcing_weights=DEFAULT_SOURCING_WEIGHTS,
        final_cfg=DEFAULT_FINAL_WEIGHTS,
        thresholds=DEFAULT_THRESHOLDS,
    )
    rng = random.Random(42)
    shuffled = list(assessments)
    rng.shuffle(shuffled)
    rows2 = build_rows(
        shuffled,
        supplier_index=index,
        candidates_report=None,
        sourcing_weights=DEFAULT_SOURCING_WEIGHTS,
        final_cfg=DEFAULT_FINAL_WEIGHTS,
        thresholds=DEFAULT_THRESHOLDS,
    )
    opps1 = rollup_opportunities(rows1)
    opps2 = rollup_opportunities(rows2)
    assert [o.best_candidate_key for o in opps1] == [
        o.best_candidate_key for o in opps2
    ]
    assert [o.top_row_keys for o in opps1] == [o.top_row_keys for o in opps2]
