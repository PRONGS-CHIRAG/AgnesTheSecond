"""
Phase 6 context expansion.

Each Phase 5 ``SubstituteEvidence`` is keyed by ``(source_key, candidate_key)``.
Recommendations, however, are per-company/product: the same substitute can be
accept/reject depending on which finished good consumes the source.

``expand_context`` walks ``company_product_tree`` (BOM joins) and fans each
evidence pair out to one :class:`AssessmentContext` per ``(company_id,
finished_product_id)`` that actually consumes the source raw material.
"""

from __future__ import annotations

import pandas as pd
import structlog
from sqlalchemy.engine import Engine

from agnes.data.queries import company_product_tree
from agnes.models.assessment import AssessmentContext
from agnes.models.canonical import CanonicalMaterial, CanonicalRegistry
from agnes.models.evidence import EvidenceReport
from agnes.models.substitutes import SubstituteCandidateReport

logger = structlog.get_logger(__name__)


def _registry_by_canonical_key(
    registry: CanonicalRegistry,
) -> dict[str, list[CanonicalMaterial]]:
    """Group canonical materials by ``canonical_key`` (stable order)."""
    return registry.by_canonical_key()


def _display_name(
    registry_index: dict[str, list[CanonicalMaterial]],
    canonical_key: str,
) -> str:
    mats = registry_index.get(canonical_key) or []
    if mats and mats[0].normalized_name:
        return mats[0].normalized_name
    return canonical_key.replace("-", " ")


def _raw_ids_for_key(
    registry_index: dict[str, list[CanonicalMaterial]],
    canonical_key: str,
) -> set[int]:
    return {m.raw_product_id for m in registry_index.get(canonical_key, [])}


def _substitute_score_lookup(
    candidates_report: SubstituteCandidateReport | None,
) -> dict[tuple[str, str], float]:
    """``(source_key, candidate_key) -> composite score`` from Phase 4."""
    if candidates_report is None:
        return {}
    out: dict[tuple[str, str], float] = {}
    for cand in candidates_report.candidates:
        key = (cand.source_key, cand.candidate_key)
        out.setdefault(key, cand.score)
    return out


def expand_context(
    registry: CanonicalRegistry,
    engine: Engine,
    evidence_report: EvidenceReport,
    *,
    candidates_report: SubstituteCandidateReport | None = None,
    usage_df: pd.DataFrame | None = None,
) -> list[AssessmentContext]:
    """
    Fan each Phase 5 evidence pair out to one tuple per (company, finished product).

    Parameters
    ----------
    registry:
        Canonical registry, used to resolve ``canonical_key`` to raw product ids
        and display names.
    engine:
        SQLAlchemy engine pointing at the challenge DB. Ignored if ``usage_df``
        is supplied (tests inject their own frame).
    evidence_report:
        Phase 5 output containing the ``(source_key, candidate_key)`` pairs.
    candidates_report:
        Optional Phase 4 report; used only to pass a composite score through.
    usage_df:
        Optional pre-fetched ``company_product_tree`` frame (test hook).
    """
    index = _registry_by_canonical_key(registry)
    scores = _substitute_score_lookup(candidates_report)

    tree = usage_df if usage_df is not None else company_product_tree(engine)
    if tree is None or tree.empty:
        logger.warning("phase6_context_empty_tree")
        return []

    tree = tree[
        ["CompanyId", "CompanyName", "FinishedProductId", "FinishedSKU", "RawProductId"]
    ].drop_duplicates()

    tuples: list[AssessmentContext] = []
    seen: set[tuple[int, int, str, str]] = set()

    for evidence in evidence_report.items:
        source_raw_ids = _raw_ids_for_key(index, evidence.source_key)
        if not source_raw_ids:
            logger.warning(
                "phase6_context_missing_source_in_registry",
                source=evidence.source_key,
            )
            continue
        rows = tree[tree["RawProductId"].isin(source_raw_ids)]
        if rows.empty:
            logger.info(
                "phase6_context_no_usage",
                source=evidence.source_key,
                candidate=evidence.candidate_key,
            )
            continue

        source_name = _display_name(index, evidence.source_key)
        candidate_name = _display_name(index, evidence.candidate_key)
        score = scores.get((evidence.source_key, evidence.candidate_key))

        companies = (
            rows[["CompanyId", "CompanyName", "FinishedProductId", "FinishedSKU"]]
            .drop_duplicates()
            .sort_values(["CompanyId", "FinishedProductId"])
        )
        for _, row in companies.iterrows():
            key = (
                int(row["CompanyId"]),
                int(row["FinishedProductId"]),
                evidence.source_key,
                evidence.candidate_key,
            )
            if key in seen:
                continue
            seen.add(key)
            tuples.append(
                AssessmentContext(
                    company_id=int(row["CompanyId"]),
                    company_name=(
                        str(row["CompanyName"])
                        if not pd.isna(row["CompanyName"])
                        else None
                    ),
                    finished_product_id=int(row["FinishedProductId"]),
                    finished_product_sku=(
                        str(row["FinishedSKU"])
                        if not pd.isna(row["FinishedSKU"])
                        else None
                    ),
                    source_key=evidence.source_key,
                    candidate_key=evidence.candidate_key,
                    source_display_name=source_name,
                    candidate_display_name=candidate_name,
                    substitute_score=score,
                )
            )

    tuples.sort(
        key=lambda c: (
            c.company_id,
            c.finished_product_id,
            c.source_key,
            c.candidate_key,
        )
    )
    logger.info(
        "phase6_context_expanded",
        n_pairs=len(evidence_report.items),
        n_tuples=len(tuples),
    )
    return tuples
