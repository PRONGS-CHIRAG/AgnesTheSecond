"""Phase 7 engine end-to-end with a stubbed polish backend."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from string import Template
from typing import cast

from agnes.config.settings import Settings
from agnes.models.assessment import SubstituteAssessment
from agnes.recommendation.builder import build_rows, rollup_opportunities
from agnes.recommendation.engine import RecommendationCache, generate_report
from agnes.recommendation.llm_polish import (
    StructuredBackend,
    StructuredResult,
    SummaryLLM,
)
from agnes.recommendation.scorer import (
    DEFAULT_FINAL_WEIGHTS,
    DEFAULT_SOURCING_WEIGHTS,
    DEFAULT_THRESHOLDS,
)
from agnes.recommendation.signals import SupplierIndex


class _Backend:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls = 0

    def generate(self, prompt: str, *, model: str) -> StructuredResult:
        self.calls += 1
        if not self._responses:
            raise AssertionError("no more scripted responses")
        return StructuredResult(text=self._responses.pop(0), model=model)


def _llm(backend: StructuredBackend) -> SummaryLLM:
    return SummaryLLM(
        Settings(openai_api_key="test"),
        model="gpt-4o-mini",
        backend=backend,
    )


def _tmpl() -> Template:
    return Template("source=$source_name candidate=$candidate_name grade=$grade")


def _assessment(source: str, candidate: str, **extra: object) -> SubstituteAssessment:
    base: dict[str, object] = {
        "company_id": 1,
        "company_name": "Acme",
        "finished_product_id": 10,
        "finished_product_sku": "SKU-10",
        "source_key": source,
        "candidate_key": candidate,
        "source_display_name": source.replace("-", " "),
        "candidate_display_name": candidate.replace("-", " "),
        "recommendation_class": "recommend",
        "acceptability": 0.9,
        "missing_information": [],
        "contradictions": [],
        "caveats": [],
        "rationale": "rules",
        "decision_path": "rules",
        "citations_used": [],
        "substitute_score": 0.7,
        "generated_at": datetime.now(UTC),
        "llm_model": None,
    }
    base.update(extra)
    return SubstituteAssessment(**base)  # type: ignore[arg-type]


def _supplier_index() -> SupplierIndex:
    return SupplierIndex(
        suppliers_by_key={
            "calcium-citrate": {1},
            "magnesium-citrate": {2, 3},
        },
        supplier_names_by_key={
            "calcium-citrate": ["Alpha"],
            "magnesium-citrate": ["Beta", "Gamma"],
        },
        suppliers_by_company={1: {2}},
        raw_ids_by_key={},
    )


def _rows_and_opps() -> tuple[list, list]:
    assessments = [_assessment("calcium-citrate", "magnesium-citrate")]
    rows = build_rows(
        assessments,
        supplier_index=_supplier_index(),
        candidates_report=None,
        sourcing_weights=DEFAULT_SOURCING_WEIGHTS,
        final_cfg=DEFAULT_FINAL_WEIGHTS,
        thresholds=DEFAULT_THRESHOLDS,
    )
    opportunities = rollup_opportunities(rows)
    return rows, opportunities


def _polish_payload(summary: str = "LLM-polished summary") -> str:
    return json.dumps({"tradeoff_summary": summary, "risk_notes": ["reviewer note"]})


def test_dry_run_skips_llm(tmp_path: Path) -> None:
    rows, opportunities = _rows_and_opps()
    backend = _Backend([])
    llm = _llm(cast(StructuredBackend, backend))
    cache = RecommendationCache(tmp_path / "phase7.json")

    report = generate_report(
        rows,
        opportunities,
        llm=llm,
        cache=cache,
        template=_tmpl(),
        weights={},
        thresholds={},
        top_n_polish=5,
        max_llm_calls=5,
        dry_run=True,
    )
    assert report.n_api_calls == 0
    assert backend.calls == 0
    assert report.opportunities[0].decision_path == "rules"


def test_top_n_limits_polish_scope(tmp_path: Path) -> None:
    assessments = [
        _assessment("src-a", "magnesium-citrate", finished_product_id=10),
        _assessment("src-b", "magnesium-citrate", finished_product_id=11),
    ]
    idx = SupplierIndex(
        suppliers_by_key={
            "src-a": {1},
            "src-b": {1},
            "magnesium-citrate": {2, 3},
        },
        supplier_names_by_key={
            "src-a": ["Alpha"],
            "src-b": ["Alpha"],
            "magnesium-citrate": ["Beta", "Gamma"],
        },
        suppliers_by_company={1: set()},
        raw_ids_by_key={},
    )
    rows = build_rows(
        assessments,
        supplier_index=idx,
        candidates_report=None,
        sourcing_weights=DEFAULT_SOURCING_WEIGHTS,
        final_cfg=DEFAULT_FINAL_WEIGHTS,
        thresholds=DEFAULT_THRESHOLDS,
    )
    opps = rollup_opportunities(rows)
    assert len(opps) == 2

    backend = _Backend([_polish_payload()])
    llm = _llm(cast(StructuredBackend, backend))
    cache = RecommendationCache(tmp_path / "phase7.json")
    report = generate_report(
        rows,
        opps,
        llm=llm,
        cache=cache,
        template=_tmpl(),
        weights={},
        thresholds={},
        top_n_polish=1,
        max_llm_calls=5,
    )
    assert report.n_api_calls == 1
    assert backend.calls == 1


def test_cache_hit_on_rerun(tmp_path: Path) -> None:
    rows, opportunities = _rows_and_opps()
    cache_path = tmp_path / "phase7.json"

    backend1 = _Backend([_polish_payload("first run")])
    llm1 = _llm(cast(StructuredBackend, backend1))
    cache1 = RecommendationCache(cache_path)
    report1 = generate_report(
        rows,
        opportunities,
        llm=llm1,
        cache=cache1,
        template=_tmpl(),
        weights={},
        thresholds={},
        top_n_polish=5,
        max_llm_calls=5,
    )
    cache1.save()
    assert report1.n_api_calls == 1

    backend2 = _Backend([])
    llm2 = _llm(cast(StructuredBackend, backend2))
    cache2 = RecommendationCache(cache_path)
    report2 = generate_report(
        rows,
        opportunities,
        llm=llm2,
        cache=cache2,
        template=_tmpl(),
        weights={},
        thresholds={},
        top_n_polish=5,
        max_llm_calls=5,
    )
    assert report2.n_api_calls == 0
    assert report2.n_cache_hits == 1
    assert backend2.calls == 0
    assert report2.opportunities[0].tradeoff_summary == "first run"


def test_budget_exhaustion_marks_partial(tmp_path: Path) -> None:
    assessments = [
        _assessment("src-a", "magnesium-citrate", finished_product_id=10),
        _assessment("src-b", "magnesium-citrate", finished_product_id=11),
    ]
    idx = SupplierIndex(
        suppliers_by_key={
            "src-a": {1},
            "src-b": {1},
            "magnesium-citrate": {2, 3},
        },
        supplier_names_by_key={
            "src-a": ["Alpha"],
            "src-b": ["Alpha"],
            "magnesium-citrate": ["Beta", "Gamma"],
        },
        suppliers_by_company={1: set()},
        raw_ids_by_key={},
    )
    rows = build_rows(
        assessments,
        supplier_index=idx,
        candidates_report=None,
        sourcing_weights=DEFAULT_SOURCING_WEIGHTS,
        final_cfg=DEFAULT_FINAL_WEIGHTS,
        thresholds=DEFAULT_THRESHOLDS,
    )
    opps = rollup_opportunities(rows)

    backend = _Backend([_polish_payload()])
    llm = _llm(cast(StructuredBackend, backend))
    cache = RecommendationCache(tmp_path / "phase7.json")
    report = generate_report(
        rows,
        opps,
        llm=llm,
        cache=cache,
        template=_tmpl(),
        weights={},
        thresholds={},
        top_n_polish=5,
        max_llm_calls=1,
    )
    assert report.n_api_calls == 1
    assert report.partial is True


def test_llm_failure_falls_back_to_deterministic(tmp_path: Path) -> None:
    rows, opportunities = _rows_and_opps()
    backend = _Backend(["garbage", "still garbage"])
    llm = _llm(cast(StructuredBackend, backend))
    cache = RecommendationCache(tmp_path / "phase7.json")

    report = generate_report(
        rows,
        opportunities,
        llm=llm,
        cache=cache,
        template=_tmpl(),
        weights={},
        thresholds={},
        top_n_polish=5,
        max_llm_calls=5,
    )
    assert report.n_failures == 1
    assert report.opportunities[0].decision_path == "rules"
    assert "Consolidate" in report.opportunities[0].tradeoff_summary
