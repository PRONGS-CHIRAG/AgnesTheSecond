"""
Phase 7 row + rollup builder.

Deterministic composition layer: given Phase 6 assessments, Phase 4 features,
and a :class:`SupplierIndex`, produce per-tuple :class:`SourcingRecommendation`
rows and source-keyed :class:`ConsolidationOpportunity` rollups.

Pure / testable: no I/O, no LLM. The optional polish pass in
:mod:`agnes.recommendation.engine` mutates these in place (via
``model_copy``) after scoring is frozen.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

import structlog

from agnes.models.assessment import SubstituteAssessment
from agnes.models.recommendation import (
    ConsolidationOpportunity,
    RecommendationGrade,
    SourcingRecommendation,
    SourcingSignals,
)
from agnes.models.substitutes import SubstituteCandidateReport
from agnes.recommendation.scorer import (
    FinalScoreConfig,
    GradeThresholds,
    ScoringInputs,
    SourcingWeights,
    final_score,
    map_grade,
    sourcing_benefit,
)
from agnes.recommendation.signals import SupplierIndex, compute_signals

logger = structlog.get_logger(__name__)

HIGH_WEIGHT_CONTRADICTION_KEYS = frozenset(
    {"functional_equivalence", "regulatory", "certification"}
)

GRADE_PRIORITY: dict[RecommendationGrade, int] = {
    "safe_to_consolidate": 3,
    "likely_safe_review_required": 2,
    "potential_substitute_insufficient_evidence": 1,
    "not_recommended": 0,
}


def _substitute_score_by_pair(
    candidates_report: SubstituteCandidateReport | None,
) -> dict[tuple[str, str], float]:
    """Fallback lookup when the assessment row doesn't carry ``substitute_score``."""
    if candidates_report is None:
        return {}
    out: dict[tuple[str, str], float] = {}
    for cand in candidates_report.candidates:
        out.setdefault((cand.source_key, cand.candidate_key), cand.score)
    return out


def _deterministic_tradeoff_summary(
    *,
    source_name: str,
    candidate_name: str,
    grade: RecommendationGrade,
    acceptability: float,
    sourcing_benefit_value: float,
    signals: SourcingSignals,
    caveats: list[str],
) -> str:
    """Short, deterministic summary used until the optional LLM polish runs."""
    lines: list[str] = []
    verdict_map = {
        "safe_to_consolidate": "Consolidation looks safe",
        "likely_safe_review_required": "Likely safe, but review recommended",
        "potential_substitute_insufficient_evidence": (
            "Potential substitute — more evidence needed"
        ),
        "not_recommended": "Not recommended",
    }
    lines.append(
        f"{verdict_map[grade]}: swap {source_name} for {candidate_name}."
    )
    lines.append(
        "Acceptability "
        f"{acceptability:.2f}, sourcing benefit {sourcing_benefit_value:.2f}."
    )
    if "no_supplier_data" in signals.missing_signals:
        lines.append("Supplier data missing — sourcing benefit is a neutral estimate.")
    else:
        lines.append(
            f"Source suppliers: {signals.source_supplier_count}, "
            f"candidate suppliers: {signals.candidate_supplier_count}, "
            f"company overlap: {signals.company_supplier_overlap:.0%}."
        )
    if caveats:
        first = caveats[0]
        trimmed = first if len(first) < 140 else first[:137] + "..."
        lines.append(f"Caveat: {trimmed}")
    return " ".join(lines)


def _risk_notes_from_assessment(
    assessment: SubstituteAssessment,
    signals: SourcingSignals,
) -> list[str]:
    """Structured risk notes surfaced on the row (UI pill-list friendly)."""
    notes: list[str] = []
    for key in assessment.contradictions:
        notes.append(f"contradiction: {key}")
    if signals.source_supplier_count <= 1:
        notes.append("single-source risk on incumbent raw")
    if signals.candidate_supplier_count == 0:
        notes.append("no known suppliers for candidate")
    if "no_supplier_data" in signals.missing_signals:
        notes.append("supplier data incomplete")
    return notes


def build_rows(
    assessments: list[SubstituteAssessment],
    *,
    supplier_index: SupplierIndex,
    candidates_report: SubstituteCandidateReport | None = None,
    sourcing_weights: SourcingWeights,
    final_cfg: FinalScoreConfig,
    thresholds: GradeThresholds,
    llm_model: str | None = None,
) -> list[SourcingRecommendation]:
    """
    Build one :class:`SourcingRecommendation` per Phase 6 assessment row.

    ``substitute_score`` is taken from the assessment; if missing, we fall back
    to the Phase 4 report. Phase 6 citations + caveats are passed through
    unchanged so reviewers can drill down.
    """
    score_lookup = _substitute_score_by_pair(candidates_report)
    rows: list[SourcingRecommendation] = []
    now = datetime.now(UTC)

    for assessment in assessments:
        signals = compute_signals(
            supplier_index,
            company_id=assessment.company_id,
            source_key=assessment.source_key,
            candidate_key=assessment.candidate_key,
        )
        benefit = sourcing_benefit(signals, sourcing_weights)
        sub_score = assessment.substitute_score
        if sub_score is None:
            sub_score = score_lookup.get(
                (assessment.source_key, assessment.candidate_key)
            )
        score_value = final_score(
            assessment.acceptability,
            sub_score,
            benefit,
            final_cfg,
        )
        has_high_weight = any(
            k in HIGH_WEIGHT_CONTRADICTION_KEYS for k in assessment.contradictions
        )
        scoring = ScoringInputs(
            acceptability=assessment.acceptability,
            substitute_score=sub_score,
            sourcing_benefit=benefit,
            signals=signals,
            has_high_weight_contradiction=has_high_weight,
            contradictions=list(assessment.contradictions),
        )
        grade, review_required = map_grade(
            assessment.recommendation_class,
            score_value,
            scoring,
            thresholds,
        )
        current_suppliers = supplier_index.supplier_names_by_key.get(
            assessment.source_key, []
        )
        recommended_suppliers = supplier_index.supplier_names_by_key.get(
            assessment.candidate_key, []
        )
        summary = _deterministic_tradeoff_summary(
            source_name=assessment.source_display_name,
            candidate_name=assessment.candidate_display_name,
            grade=grade,
            acceptability=assessment.acceptability,
            sourcing_benefit_value=benefit,
            signals=signals,
            caveats=list(assessment.caveats),
        )
        risk_notes = _risk_notes_from_assessment(assessment, signals)
        row = SourcingRecommendation(
            company_id=assessment.company_id,
            company_name=assessment.company_name,
            finished_product_id=assessment.finished_product_id,
            finished_product_sku=assessment.finished_product_sku,
            source_key=assessment.source_key,
            candidate_key=assessment.candidate_key,
            source_display_name=assessment.source_display_name,
            candidate_display_name=assessment.candidate_display_name,
            recommendation_grade=grade,
            final_score=round(score_value, 4),
            acceptability=round(assessment.acceptability, 4),
            substitute_score=(
                None if sub_score is None else round(max(0.0, min(1.0, sub_score)), 4)
            ),
            sourcing_benefit=round(benefit, 4),
            signals=signals,
            current_suppliers=list(current_suppliers),
            recommended_suppliers=list(recommended_suppliers),
            caveats=list(assessment.caveats),
            risk_notes=risk_notes,
            review_required=review_required,
            tradeoff_summary=summary,
            citations=list(assessment.citations_used),
            decision_path=assessment.decision_path,
            generated_at=now,
            llm_model=llm_model if assessment.decision_path == "llm" else None,
        )
        rows.append(row)
        logger.info(
            "phase7_row_scored",
            company_id=row.company_id,
            product_id=row.finished_product_id,
            source=row.source_key,
            candidate=row.candidate_key,
            grade=row.recommendation_grade,
            final_score=row.final_score,
            sourcing_benefit=row.sourcing_benefit,
        )

    rows.sort(
        key=lambda r: (
            r.source_key,
            -r.final_score,
            -r.acceptability,
            r.candidate_key,
            r.company_id,
            r.finished_product_id,
        )
    )
    return rows


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _best_candidate(
    rows_for_source: list[SourcingRecommendation],
) -> tuple[str, str, list[SourcingRecommendation]]:
    """
    Pick the candidate that maximizes ``sum(final_score * acceptability)``.

    Ties broken lexically on ``candidate_key`` for determinism.
    """
    per_candidate: dict[str, list[SourcingRecommendation]] = defaultdict(list)
    for row in rows_for_source:
        per_candidate[row.candidate_key].append(row)

    def _score(candidate_rows: list[SourcingRecommendation]) -> float:
        return sum(r.final_score * r.acceptability for r in candidate_rows)

    best_key = max(
        per_candidate.keys(),
        key=lambda k: (_score(per_candidate[k]), -len(per_candidate[k]), k),
    )
    chosen = per_candidate[best_key]
    best_display = chosen[0].candidate_display_name
    return best_key, best_display, chosen


def _rollup_grade(
    rows: list[SourcingRecommendation],
) -> RecommendationGrade:
    """The 'worst' grade across the chosen candidate's rows — demo-conservative."""
    worst = min(rows, key=lambda r: GRADE_PRIORITY[r.recommendation_grade])
    return worst.recommendation_grade


def rollup_opportunities(
    rows: list[SourcingRecommendation],
) -> list[ConsolidationOpportunity]:
    """Group per-tuple rows by ``source_key`` into consolidation opportunities."""
    by_source: dict[str, list[SourcingRecommendation]] = defaultdict(list)
    for row in rows:
        by_source[row.source_key].append(row)

    now = datetime.now(UTC)
    opportunities: list[ConsolidationOpportunity] = []
    for source_key in sorted(by_source.keys()):
        source_rows = by_source[source_key]
        best_key, best_display, chosen_rows = _best_candidate(source_rows)
        products = {r.finished_product_id for r in chosen_rows}
        companies = {r.company_id for r in chosen_rows}
        agg_final = (
            sum(r.final_score for r in chosen_rows) / len(chosen_rows)
            if chosen_rows
            else 0.0
        )
        agg_sourcing = (
            sum(r.sourcing_benefit for r in chosen_rows) / len(chosen_rows)
            if chosen_rows
            else 0.0
        )
        current = _dedupe_preserve_order(
            [s for r in chosen_rows for s in r.current_suppliers]
        )
        recommended = _dedupe_preserve_order(
            [s for r in chosen_rows for s in r.recommended_suppliers]
        )
        review = any(r.review_required for r in chosen_rows)
        grade = _rollup_grade(chosen_rows)
        risk_notes = _dedupe_preserve_order(
            [note for r in chosen_rows for note in r.risk_notes]
        )
        top_rows_sorted = sorted(
            chosen_rows,
            key=lambda r: (-r.final_score, r.company_id, r.finished_product_id),
        )
        top_row_keys = [r.row_key() for r in top_rows_sorted]

        summary_line = (
            f"Consolidate {source_rows[0].source_display_name} onto "
            f"{best_display} across {len(products)} product(s) "
            f"and {len(companies)} compan{'y' if len(companies) == 1 else 'ies'}. "
            f"Average acceptability "
            f"{sum(r.acceptability for r in chosen_rows) / len(chosen_rows):.2f}, "
            f"final score {agg_final:.2f}."
        )
        opportunities.append(
            ConsolidationOpportunity(
                source_key=source_key,
                source_display_name=source_rows[0].source_display_name,
                best_candidate_key=best_key,
                best_candidate_display_name=best_display,
                n_products_covered=len(products),
                n_companies_covered=len(companies),
                aggregate_final_score=round(agg_final, 4),
                aggregate_sourcing_benefit=round(agg_sourcing, 4),
                recommendation_grade=grade,
                unique_current_suppliers=current,
                unique_recommended_suppliers=recommended,
                review_required=review,
                tradeoff_summary=summary_line,
                risk_notes=risk_notes,
                top_row_keys=top_row_keys,
                decision_path="rules",
                generated_at=now,
                llm_model=None,
            )
        )
        logger.info(
            "phase7_opportunity_built",
            source=source_key,
            best_candidate=best_key,
            n_products=len(products),
            n_companies=len(companies),
            aggregate_final_score=round(agg_final, 4),
            grade=grade,
        )
    opportunities.sort(key=lambda o: (-o.aggregate_final_score, o.source_key))
    return opportunities
