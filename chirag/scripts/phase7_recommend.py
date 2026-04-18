#!/usr/bin/env python3
"""Phase 7: turn Phase 6 assessments into ranked sourcing recommendations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from agnes.config.settings import Settings
from agnes.data.db_loader import get_engine
from agnes.data.queries import raw_material_suppliers, supplier_products_by_company
from agnes.models.assessment import AssessmentReport
from agnes.models.canonical import CanonicalRegistry
from agnes.models.recommendation import (
    ConsolidationOpportunity,
    RecommendationGrade,
    RecommendationReport,
    SourcingRecommendation,
)
from agnes.models.substitutes import SubstituteCandidateReport
from agnes.recommendation.builder import build_rows, rollup_opportunities
from agnes.recommendation.engine import (
    DEFAULT_CACHE_PATH,
    RecommendationCache,
    generate_report,
)
from agnes.recommendation.llm_polish import (
    DEFAULT_PROMPT_PATH,
    SummaryLLM,
    load_prompt_template,
)
from agnes.recommendation.scorer import (
    DEFAULT_WEIGHTS,
    GradeThresholds,
    PrioritizationWeights,
)
from agnes.recommendation.signals import build_supplier_index
from agnes.utils.logging import configure_logging

OUT_DIR = Path("outputs/reports")

GRADE_RANK: dict[RecommendationGrade, int] = {
    "not_recommended": 0,
    "potential_substitute_insufficient_evidence": 1,
    "likely_safe_review_required": 2,
    "safe_to_consolidate": 3,
}


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run Phase 7 recommendation engine over Phase 6 assessments.",
    )
    p.add_argument(
        "--assessments",
        type=Path,
        default=Path("outputs/reports/substitute_assessments.json"),
        help="Phase 6 AssessmentReport input.",
    )
    p.add_argument(
        "--candidates",
        type=Path,
        default=Path("outputs/reports/substitute_candidates.json"),
        help="Phase 4 report (for fallback substitute_score passthrough).",
    )
    p.add_argument(
        "--registry",
        type=Path,
        default=Path("outputs/reports/canonical_registry.json"),
        help="Phase 2 CanonicalRegistry.",
    )
    p.add_argument(
        "--top-n-polish",
        type=int,
        default=None,
        help="Number of top opportunities to polish with the LLM.",
    )
    p.add_argument(
        "--max-llm-calls",
        type=int,
        default=None,
        help="Hard cap on new LLM calls (default: settings.phase7_max_llm_calls).",
    )
    p.add_argument(
        "--model",
        type=str,
        default=None,
        help="Polish-LLM model id (default: settings.phase7_llm_model).",
    )
    p.add_argument(
        "--prompt",
        type=Path,
        default=DEFAULT_PROMPT_PATH,
        help="Path to the Phase 7 polish prompt template.",
    )
    p.add_argument(
        "--cache-path",
        type=Path,
        default=DEFAULT_CACHE_PATH,
        help="Path to the Phase 7 disk cache.",
    )
    p.add_argument(
        "--no-cache",
        action="store_true",
        help="Do not persist the polish cache back to disk.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip LLM polish entirely (deterministic output only).",
    )
    p.add_argument(
        "--source",
        type=str,
        default=None,
        help="Restrict to one source canonical_key.",
    )
    p.add_argument(
        "--company",
        type=int,
        default=None,
        help="Restrict to one CompanyId.",
    )
    p.add_argument(
        "--min-grade",
        type=str,
        choices=list(GRADE_RANK.keys()),
        default=None,
        help="Drop rows whose recommendation_grade is weaker than this value.",
    )
    return p.parse_args()


def _merge_weights(defaults: dict[str, float], raw: str) -> dict[str, float]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return dict(defaults)
    if not isinstance(parsed, dict):
        return dict(defaults)
    merged = dict(defaults)
    for k, v in parsed.items():
        try:
            merged[str(k)] = float(v)
        except (TypeError, ValueError):
            continue
    return merged


def _prioritization_weights(settings: Settings) -> PrioritizationWeights:
    merged = _merge_weights(
        DEFAULT_WEIGHTS.as_dict(), settings.phase7_prioritization_weights
    )
    return PrioritizationWeights(
        consolidation_benefit=merged.get(
            "consolidation_benefit", DEFAULT_WEIGHTS.consolidation_benefit
        ),
        evidence_confidence=merged.get(
            "evidence_confidence", DEFAULT_WEIGHTS.evidence_confidence
        ),
        compliance_fit=merged.get(
            "compliance_fit", DEFAULT_WEIGHTS.compliance_fit
        ),
        supplier_diversification=merged.get(
            "supplier_diversification", DEFAULT_WEIGHTS.supplier_diversification
        ),
        switching_feasibility=merged.get(
            "switching_feasibility", DEFAULT_WEIGHTS.switching_feasibility
        ),
    )


def _rows_csv(path: Path, items: list[SourcingRecommendation]) -> None:
    rows = []
    for item in items:
        rows.append(
            {
                "company_id": item.company_id,
                "company_name": item.company_name or "",
                "finished_product_id": item.finished_product_id,
                "finished_product_sku": item.finished_product_sku or "",
                "source_key": item.source_key,
                "candidate_key": item.candidate_key,
                "source_display_name": item.source_display_name,
                "candidate_display_name": item.candidate_display_name,
                "recommendation_grade": item.recommendation_grade,
                "final_score": item.final_score,
                "acceptability": item.acceptability,
                "substitute_score": (
                    "" if item.substitute_score is None else item.substitute_score
                ),
                "sourcing_benefit": item.sourcing_benefit,
                "dim_consolidation_benefit": item.dimension_scores.consolidation_benefit,
                "dim_evidence_confidence": item.dimension_scores.evidence_confidence,
                "dim_compliance_fit": item.dimension_scores.compliance_fit,
                "dim_supplier_diversification": item.dimension_scores.supplier_diversification,
                "dim_switching_feasibility": item.dimension_scores.switching_feasibility,
                "concentration_risk_downgrade": item.concentration_risk_downgrade,
                "source_supplier_count": item.signals.source_supplier_count,
                "candidate_supplier_count": item.signals.candidate_supplier_count,
                "company_supplier_overlap": item.signals.company_supplier_overlap,
                "concentration_relief": item.signals.concentration_relief,
                "current_suppliers": json.dumps(item.current_suppliers),
                "recommended_suppliers": json.dumps(item.recommended_suppliers),
                "review_required": item.review_required,
                "tradeoff_summary": item.tradeoff_summary,
                "risk_notes": json.dumps(item.risk_notes),
                "caveats": json.dumps(item.caveats),
                "citations": json.dumps([c.url for c in item.citations]),
                "decision_path": item.decision_path,
                "llm_model": item.llm_model or "",
                "generated_at": item.generated_at.isoformat(),
            }
        )
    if rows:
        pd.DataFrame(rows).to_csv(path, index=False)
    else:
        path.write_text("", encoding="utf-8")


def _opportunities_csv(path: Path, opps: list[ConsolidationOpportunity]) -> None:
    rows = []
    for opp in opps:
        rows.append(
            {
                "source_key": opp.source_key,
                "source_display_name": opp.source_display_name,
                "best_candidate_key": opp.best_candidate_key,
                "best_candidate_display_name": opp.best_candidate_display_name,
                "recommendation_grade": opp.recommendation_grade,
                "n_products_covered": opp.n_products_covered,
                "n_companies_covered": opp.n_companies_covered,
                "aggregate_final_score": opp.aggregate_final_score,
                "aggregate_sourcing_benefit": opp.aggregate_sourcing_benefit,
                "agg_consolidation_benefit": opp.aggregate_dimension_scores.consolidation_benefit,
                "agg_evidence_confidence": opp.aggregate_dimension_scores.evidence_confidence,
                "agg_compliance_fit": opp.aggregate_dimension_scores.compliance_fit,
                "agg_supplier_diversification": (
                    opp.aggregate_dimension_scores.supplier_diversification
                ),
                "agg_switching_feasibility": opp.aggregate_dimension_scores.switching_feasibility,
                "any_concentration_risk_downgrade": opp.any_concentration_risk_downgrade,
                "review_required": opp.review_required,
                "tradeoff_summary": opp.tradeoff_summary,
                "risk_notes": json.dumps(opp.risk_notes),
                "unique_current_suppliers": json.dumps(opp.unique_current_suppliers),
                "unique_recommended_suppliers": json.dumps(
                    opp.unique_recommended_suppliers
                ),
                "top_row_keys": json.dumps(opp.top_row_keys),
                "decision_path": opp.decision_path,
                "llm_model": opp.llm_model or "",
                "generated_at": opp.generated_at.isoformat(),
            }
        )
    if rows:
        pd.DataFrame(rows).to_csv(path, index=False)
    else:
        path.write_text("", encoding="utf-8")


def _filter_rows(
    rows: list[SourcingRecommendation],
    *,
    source: str | None,
    company: int | None,
    min_grade: str | None,
) -> list[SourcingRecommendation]:
    out = rows
    if source:
        out = [r for r in out if r.source_key == source]
    if company is not None:
        out = [r for r in out if r.company_id == company]
    if min_grade:
        threshold = GRADE_RANK[min_grade]  # type: ignore[index]
        out = [r for r in out if GRADE_RANK[r.recommendation_grade] >= threshold]
    return out


def _summary_line(report: RecommendationReport, json_path: Path) -> str:
    return json.dumps(
        {
            "ok": True,
            "n_tuples": report.n_tuples,
            "n_opportunities": report.n_opportunities,
            "n_cache_hits": report.n_cache_hits,
            "n_api_calls": report.n_api_calls,
            "n_failures": report.n_failures,
            "counts_by_grade": report.counts_by_grade,
            "partial": report.partial,
            "duration_ms": report.duration_ms,
            "llm_model": report.llm_model,
            "report": str(json_path),
        }
    )


def main() -> int:  # noqa: PLR0915
    args = _parse_args()
    settings = Settings()
    configure_logging(settings.log_level)

    for label, path in (
        ("assessments_missing", args.assessments),
        ("registry_missing", args.registry),
    ):
        if not path.is_file():
            print(json.dumps({"error": label, "path": str(path)}), file=sys.stderr)
            return 1

    assessment_report = AssessmentReport.model_validate_json(
        args.assessments.read_text(encoding="utf-8")
    )
    registry = CanonicalRegistry.model_validate_json(
        args.registry.read_text(encoding="utf-8")
    )
    candidates_report: SubstituteCandidateReport | None = None
    if args.candidates.is_file():
        candidates_report = SubstituteCandidateReport.model_validate_json(
            args.candidates.read_text(encoding="utf-8")
        )

    if not assessment_report.items:
        print(
            json.dumps(
                {"ok": False, "reason": "no_assessments", "hint": "re-run phase 6"}
            )
        )
        return 0

    engine = get_engine(settings)
    suppliers_df = raw_material_suppliers(engine)
    company_df = supplier_products_by_company(engine)
    index = build_supplier_index(registry, suppliers_df, company_df)

    prioritization_weights = _prioritization_weights(settings)
    thresholds = GradeThresholds(
        safe=settings.phase7_safe_threshold,
        reject=settings.phase7_reject_threshold,
        diversification_floor=settings.phase7_diversification_floor,
    )

    rows = build_rows(
        assessment_report.items,
        supplier_index=index,
        candidates_report=candidates_report,
        prioritization_weights=prioritization_weights,
        thresholds=thresholds,
        llm_model=assessment_report.llm_model,
    )
    rows = _filter_rows(
        rows,
        source=args.source,
        company=args.company,
        min_grade=args.min_grade,
    )
    opportunities = rollup_opportunities(rows)

    top_n_polish = (
        args.top_n_polish
        if args.top_n_polish is not None
        else settings.phase7_top_n_polish
    )
    max_llm_calls = (
        args.max_llm_calls
        if args.max_llm_calls is not None
        else settings.phase7_max_llm_calls
    )
    model_id = args.model or settings.phase7_llm_model

    llm: SummaryLLM | None = None
    template = None
    if not args.dry_run and max_llm_calls > 0 and top_n_polish > 0:
        template = load_prompt_template(args.prompt)
        llm = SummaryLLM(settings, model=model_id)

    cache = RecommendationCache(args.cache_path)
    weights_blob = prioritization_weights.as_dict()
    thresholds_blob = thresholds.as_dict()

    report = generate_report(
        rows,
        opportunities,
        llm=llm,
        cache=cache,
        template=template,
        weights=weights_blob,
        thresholds=thresholds_blob,
        top_n_polish=top_n_polish,
        max_llm_calls=max_llm_calls,
        dry_run=args.dry_run,
    )

    if not args.no_cache and not args.dry_run:
        cache.save()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / "sourcing_recommendations.json"
    rows_csv_path = OUT_DIR / "sourcing_recommendations.csv"
    opps_csv_path = OUT_DIR / "consolidation_opportunities.csv"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    _rows_csv(rows_csv_path, report.items)
    _opportunities_csv(opps_csv_path, report.opportunities)

    print(_summary_line(report, json_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
