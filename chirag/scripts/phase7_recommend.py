#!/usr/bin/env python3
"""Phase 7: turn Phase 6 assessments into ranked sourcing recommendations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from agnes.canonicalization.taxonomy import TAXONOMY_VERSION  # noqa: F401
from agnes.config.settings import Settings
from agnes.data.db_loader import (
    get_engine,
    load_price_benchmarks,
    load_procurement_history,
    load_supplier_ratings,
    procurement_tables_present,
)
from agnes.data.queries import (
    load_suppliers,
    raw_material_suppliers,
    supplier_products_by_company,
)
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
    DEFAULT_FINAL_WEIGHTS,
    DEFAULT_SOURCING_WEIGHTS,
    FinalScoreConfig,
    GradeThresholds,
    SourcingWeights,
)
from agnes.recommendation.signals import build_supplier_index
from agnes.services.cost import (
    CostSignal,
    build_supplier_pricing,
    compute_cost_signal,
)
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


def _sourcing_weights(settings: Settings) -> SourcingWeights:
    merged = _merge_weights(
        DEFAULT_SOURCING_WEIGHTS.as_dict(), settings.phase7_sourcing_weights
    )
    return SourcingWeights(
        diversification=merged.get(
            "diversification", DEFAULT_SOURCING_WEIGHTS.diversification
        ),
        company_overlap=merged.get(
            "company_overlap", DEFAULT_SOURCING_WEIGHTS.company_overlap
        ),
        concentration_relief=merged.get(
            "concentration_relief", DEFAULT_SOURCING_WEIGHTS.concentration_relief
        ),
    )


def _final_weights(settings: Settings) -> FinalScoreConfig:
    merged = _merge_weights(
        DEFAULT_FINAL_WEIGHTS.as_dict(), settings.phase7_final_weights
    )
    return FinalScoreConfig(
        alpha_acceptability=merged.get(
            "acceptability", DEFAULT_FINAL_WEIGHTS.alpha_acceptability
        ),
        alpha_substitute=merged.get(
            "substitute", DEFAULT_FINAL_WEIGHTS.alpha_substitute
        ),
        alpha_sourcing=merged.get("sourcing", DEFAULT_FINAL_WEIGHTS.alpha_sourcing),
        alpha_savings=merged.get("savings", DEFAULT_FINAL_WEIGHTS.alpha_savings),
    )


def _build_cost_signals(
    settings: Settings,
    registry: CanonicalRegistry,
) -> dict[str, CostSignal]:
    """Compute a :class:`CostSignal` per canonical key, if procurement data is present.

    Returns an empty dict when any required table is missing — Phase 7 then
    degrades gracefully to the 3-signal behaviour (sourcing + acceptability +
    substitute_score).
    """
    engine = get_engine(settings)
    if not procurement_tables_present(engine):
        return {}

    ratings_by_supplier = load_supplier_ratings(engine, settings)
    benchmark_by_base = load_price_benchmarks(engine, settings)
    orders = list(load_procurement_history(engine, settings))
    if not orders:
        return {}

    suppliers_df = load_suppliers(engine)
    supplier_names: dict[int, str] = {
        int(row["Id"]): str(row["Name"]) for _, row in suppliers_df.iterrows()
    }

    orders_by_product: dict[int, list] = {}
    for o in orders:
        orders_by_product.setdefault(o.ProductId, []).append(o)

    raw_ids_by_key: dict[str, set[int]] = {}
    bases_by_key: dict[str, str] = {}
    labels_by_key: dict[str, str] = {}
    for m in registry.materials:
        raw_ids_by_key.setdefault(m.canonical_key, set()).add(m.raw_product_id)
        bases_by_key.setdefault(m.canonical_key, m.canonical_key.split("::")[-1])
        labels_by_key.setdefault(m.canonical_key, m.normalized_name)

    out: dict[str, CostSignal] = {}
    for canonical_key, raw_ids in raw_ids_by_key.items():
        key_orders = [o for rid in raw_ids for o in orders_by_product.get(rid, [])]
        if not key_orders:
            continue
        pricings = build_supplier_pricing(
            key_orders,
            ratings_by_supplier=ratings_by_supplier,
            supplier_names=supplier_names,
        )
        benchmark = benchmark_by_base.get(bases_by_key.get(canonical_key, ""))
        out[canonical_key] = compute_cost_signal(
            pricings,
            benchmark=benchmark,
            ingredient_label=labels_by_key.get(canonical_key),
        )
    return out


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
                "savings_signal": item.savings_signal,
                "estimated_savings_usd": (
                    "" if item.estimated_savings_usd is None else item.estimated_savings_usd
                ),
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
                "aggregate_savings_signal": opp.aggregate_savings_signal,
                "total_estimated_savings_usd": opp.total_estimated_savings_usd,
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

    sourcing_weights = _sourcing_weights(settings)
    final_cfg = _final_weights(settings)
    thresholds = GradeThresholds(
        safe=settings.phase7_safe_threshold,
        reject=settings.phase7_reject_threshold,
    )

    cost_signal_by_key = _build_cost_signals(settings, registry)

    rows = build_rows(
        assessment_report.items,
        supplier_index=index,
        candidates_report=candidates_report,
        sourcing_weights=sourcing_weights,
        final_cfg=final_cfg,
        thresholds=thresholds,
        llm_model=assessment_report.llm_model,
        cost_signal_by_key=cost_signal_by_key,
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
    weights_blob = {
        **{f"sourcing.{k}": v for k, v in sourcing_weights.as_dict().items()},
        **{f"final.{k}": v for k, v in final_cfg.as_dict().items()},
    }
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
