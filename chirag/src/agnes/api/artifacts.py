"""Read-only endpoints exposing Phase 1-7 report artifacts.

All responses are Pydantic-validated at load time. Missing reports return 404
with a structured ``detail`` payload so the frontend can render a graceful
"phase has never been run" state rather than a generic error.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict

from agnes.api.services.artifact_loader import ArtifactLoader, ArtifactMissingError
from agnes.api.services.supply_network import SupplyNetworkService
from agnes.models.assessment import AssessmentReport, SubstituteAssessment
from agnes.models.canonical import CanonicalMaterial
from agnes.models.evidence import EvidenceReport, SubstituteEvidence
from agnes.models.recommendation import (
    ConsolidationOpportunity,
    RecommendationReport,
    SourcingRecommendation,
)
from agnes.models.substitutes import SubstituteCandidate, SubstituteCandidateReport
from agnes.models.supply_network import SupplyNetworkBundle

router = APIRouter(prefix="/api", tags=["artifacts"])


# ---------- response envelopes ----------


class ArtifactStatusOut(BaseModel):
    name: str
    present: bool
    path: str
    size_bytes: int | None = None
    mtime_ns: int | None = None
    generated_at: datetime | None = None


class SummaryOut(BaseModel):
    artifacts: list[ArtifactStatusOut]
    canonical: dict[str, Any] | None = None
    candidates: dict[str, Any] | None = None
    evidence: dict[str, Any] | None = None
    assessments: dict[str, Any] | None = None
    recommendations: dict[str, Any] | None = None


class RegistryPageOut(BaseModel):
    total: int
    limit: int
    offset: int
    q: str | None
    family: str | None
    role: str | None
    families: list[str]
    roles: list[str]
    items: list[CanonicalMaterial]


class OpportunityDetailOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opportunity: ConsolidationOpportunity
    rows: list[SourcingRecommendation]
    evidence: list[SubstituteEvidence]
    assessments: list[SubstituteAssessment]
    candidates: list[SubstituteCandidate]


class ConfidenceBucket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bucket: str
    lo: float
    hi: float
    n: int


class RegistryBundle(BaseModel):
    """Full canonical registry + server-computed aggregates for the dashboard."""

    model_config = ConfigDict(extra="forbid")

    total: int
    families: list[str]
    roles: list[str]
    family_counts: dict[str, int]
    role_counts: dict[str, int]
    confidence_histogram: list[ConfidenceBucket]
    taxonomy_version: str | None = None
    generated_at: datetime | None = None
    coverage: dict[str, int] | None = None
    unique_canonical_keys: int | None = None
    items: list[CanonicalMaterial]


class DashboardBundle(BaseModel):
    """One-shot payload powering the command-center dashboard."""

    model_config = ConfigDict(extra="forbid")

    summary: SummaryOut
    registry: RegistryBundle | None = None
    candidates: SubstituteCandidateReport | None = None
    evidence: EvidenceReport | None = None
    assessments: AssessmentReport | None = None
    recommendations: RecommendationReport | None = None
    opportunity_details: list[OpportunityDetailOut]
    supply_network: SupplyNetworkBundle | None = None
    missing: list[str]


# ---------- helpers ----------


def _loader(request: Request) -> ArtifactLoader:
    loader: ArtifactLoader = request.app.state.artifact_loader
    return loader


def _supply_network_service(request: Request) -> SupplyNetworkService:
    svc: SupplyNetworkService = request.app.state.supply_network_service
    return svc


def _status_out(
    loader: ArtifactLoader, name: str, generated_at: datetime | None
) -> ArtifactStatusOut:
    st = loader.status(name)
    return ArtifactStatusOut(
        name=name,
        present=st.present,
        path=str(st.path),
        size_bytes=st.size_bytes,
        mtime_ns=st.mtime_ns,
        generated_at=generated_at,
    )


def _row_key(row: SourcingRecommendation | SubstituteAssessment) -> str:
    return f"{row.company_id}|{row.finished_product_id}|{row.source_key}|{row.candidate_key}"


def _missing(name: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"error": "artifact_missing", "artifact": name},
    )


_CONFIDENCE_BUCKETS: tuple[tuple[str, float, float], ...] = (
    ("0.00–0.20", 0.0, 0.20),
    ("0.20–0.40", 0.20, 0.40),
    ("0.40–0.60", 0.40, 0.60),
    ("0.60–0.80", 0.60, 0.80),
    ("0.80–1.00", 0.80, 1.0001),
)


def _build_summary(
    loader: ArtifactLoader,
) -> tuple[SummaryOut, dict[str, datetime | None], list[str]]:
    """Shared helper for /api/summary and /api/dashboard.

    Returns the summary, a per-name generated_at map, and the list of missing
    artifact names so callers can branch on what to include.
    """
    out = SummaryOut(artifacts=[])
    gen_by_name: dict[str, datetime | None] = {name: None for name in loader.all_statuses()}
    missing: list[str] = []

    try:
        reg = loader.get_registry()
        gen_by_name["registry"] = reg.generated_at
        out.canonical = {
            "unique_canonical_keys": reg.unique_canonical_keys,
            "assigned": reg.coverage.assigned,
            "unassigned": reg.coverage.unassigned,
            "parse_failed": reg.coverage.parse_failed,
            "materials": len(reg.materials),
            "taxonomy_version": reg.taxonomy_version,
        }
    except ArtifactMissingError:
        missing.append("registry")

    try:
        cands = loader.get_candidates()
        gen_by_name["candidates"] = cands.generated_at
        out.candidates = {
            "n_targets": cands.n_targets,
            "n_with_candidates": cands.n_with_candidates,
            "n_without_candidates": cands.n_without_candidates,
            "avg_top_score": cands.avg_top_score,
            "top_k": cands.top_k,
            "min_score": cands.min_score,
            "embedding_model": cands.embedding_model,
            "partial": cands.partial,
            "n_candidates": len(cands.candidates),
        }
    except ArtifactMissingError:
        missing.append("candidates")

    try:
        ev = loader.get_evidence()
        gen_by_name["evidence"] = ev.generated_at
        out.evidence = {
            "n_pairs": ev.n_pairs,
            "n_sources": ev.n_sources,
            "n_cache_hits": ev.n_cache_hits,
            "n_api_calls": ev.n_api_calls,
            "n_failures": ev.n_failures,
            "partial": ev.partial,
            "llm_model": ev.llm_model,
        }
    except ArtifactMissingError:
        missing.append("evidence")

    try:
        asmt = loader.get_assessments()
        gen_by_name["assessments"] = asmt.generated_at
        out.assessments = {
            "n_tuples": asmt.n_tuples,
            "n_rules_decisions": asmt.n_rules_decisions,
            "n_llm_decisions": asmt.n_llm_decisions,
            "n_cache_hits": asmt.n_cache_hits,
            "n_api_calls": asmt.n_api_calls,
            "n_failures": asmt.n_failures,
            "n_without_evidence": asmt.n_without_evidence,
            "counts_by_class": dict(asmt.counts_by_class),
            "partial": asmt.partial,
            "llm_model": asmt.llm_model,
        }
    except ArtifactMissingError:
        missing.append("assessments")

    try:
        rec = loader.get_recommendations()
        gen_by_name["recommendations"] = rec.generated_at
        out.recommendations = {
            "n_tuples": rec.n_tuples,
            "n_opportunities": rec.n_opportunities,
            "n_cache_hits": rec.n_cache_hits,
            "n_api_calls": rec.n_api_calls,
            "n_failures": rec.n_failures,
            "counts_by_grade": dict(rec.counts_by_grade),
            "partial": rec.partial,
            "llm_model": rec.llm_model,
        }
    except ArtifactMissingError:
        missing.append("recommendations")

    out.artifacts = [
        _status_out(loader, name, gen_by_name.get(name))
        for name in loader.all_statuses()
    ]
    return out, gen_by_name, missing


def _build_registry_bundle(loader: ArtifactLoader) -> RegistryBundle | None:
    try:
        reg = loader.get_registry()
    except ArtifactMissingError:
        return None
    fam_counts: dict[str, int] = {}
    role_counts: dict[str, int] = {}
    hist = [0] * len(_CONFIDENCE_BUCKETS)
    for m in reg.materials:
        fam_counts[m.ingredient_family] = fam_counts.get(m.ingredient_family, 0) + 1
        role_counts[m.functional_role] = role_counts.get(m.functional_role, 0) + 1
        c = float(m.confidence)
        for i, (_, lo, hi) in enumerate(_CONFIDENCE_BUCKETS):
            if lo <= c < hi:
                hist[i] += 1
                break
    buckets = [
        ConfidenceBucket(bucket=label, lo=lo, hi=min(hi, 1.0), n=hist[i])
        for i, (label, lo, hi) in enumerate(_CONFIDENCE_BUCKETS)
    ]
    return RegistryBundle(
        total=len(reg.materials),
        families=sorted(fam_counts),
        roles=sorted(role_counts),
        family_counts=dict(sorted(fam_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        role_counts=dict(sorted(role_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        confidence_histogram=buckets,
        taxonomy_version=reg.taxonomy_version,
        generated_at=reg.generated_at,
        coverage={
            "assigned": reg.coverage.assigned,
            "unassigned": reg.coverage.unassigned,
            "parse_failed": reg.coverage.parse_failed,
        },
        unique_canonical_keys=reg.unique_canonical_keys,
        items=list(reg.materials),
    )


def _build_opportunity_detail(
    loader: ArtifactLoader,
    opp: ConsolidationOpportunity,
    recommendations: RecommendationReport,
) -> OpportunityDetailOut:
    rows = [r for r in recommendations.items if r.source_key == opp.source_key]
    candidate_keys = {r.candidate_key for r in rows}

    try:
        evidence = [
            e
            for e in loader.get_evidence().items
            if e.source_key == opp.source_key and e.candidate_key in candidate_keys
        ]
    except ArtifactMissingError:
        evidence = []

    try:
        assessments = [
            a
            for a in loader.get_assessments().items
            if a.source_key == opp.source_key and a.candidate_key in candidate_keys
        ]
    except ArtifactMissingError:
        assessments = []

    try:
        candidates = [
            c
            for c in loader.get_candidates().candidates
            if c.source_key == opp.source_key and c.candidate_key in candidate_keys
        ]
    except ArtifactMissingError:
        candidates = []

    return OpportunityDetailOut(
        opportunity=opp,
        rows=rows,
        evidence=evidence,
        assessments=assessments,
        candidates=candidates,
    )


# ---------- endpoints ----------


@router.get("/summary", response_model=SummaryOut)
def get_summary(request: Request) -> SummaryOut:
    loader = _loader(request)
    summary, _, _ = _build_summary(loader)
    return summary


@router.get("/registry", response_model=RegistryPageOut)
def get_registry(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    q: str | None = None,
    family: str | None = None,
    role: str | None = None,
) -> RegistryPageOut:
    loader = _loader(request)
    try:
        reg = loader.get_registry()
    except ArtifactMissingError as exc:
        raise _missing("registry") from exc

    materials = reg.materials
    needle = q.strip().lower() if q else ""

    def _matches(m: CanonicalMaterial) -> bool:
        if family and m.ingredient_family != family:
            return False
        if role and m.functional_role != role:
            return False
        if needle:
            hay = f"{m.normalized_name} {m.canonical_key} {m.sku}".lower()
            if needle not in hay:
                return False
        return True

    filtered = [m for m in materials if _matches(m)]
    page = filtered[offset : offset + limit]
    families = sorted({m.ingredient_family for m in materials})
    roles = sorted({m.functional_role for m in materials})

    return RegistryPageOut(
        total=len(filtered),
        limit=limit,
        offset=offset,
        q=q,
        family=family,
        role=role,
        families=families,
        roles=roles,
        items=page,
    )


@router.get("/registry/{canonical_key}", response_model=list[CanonicalMaterial])
def get_registry_key(request: Request, canonical_key: str) -> list[CanonicalMaterial]:
    loader = _loader(request)
    try:
        reg = loader.get_registry()
    except ArtifactMissingError as exc:
        raise _missing("registry") from exc
    rows = [m for m in reg.materials if m.canonical_key == canonical_key]
    if not rows:
        raise HTTPException(
            status_code=404,
            detail={"error": "canonical_key_not_found", "canonical_key": canonical_key},
        )
    return rows


@router.get("/candidates", response_model=SubstituteCandidateReport)
def get_candidates(request: Request) -> SubstituteCandidateReport:
    loader = _loader(request)
    try:
        return loader.get_candidates()
    except ArtifactMissingError as exc:
        raise _missing("candidates") from exc


@router.get("/evidence", response_model=EvidenceReport)
def get_evidence(request: Request) -> EvidenceReport:
    loader = _loader(request)
    try:
        return loader.get_evidence()
    except ArtifactMissingError as exc:
        raise _missing("evidence") from exc


@router.get("/evidence/{source_key}/{candidate_key}", response_model=SubstituteEvidence)
def get_evidence_pair(
    request: Request, source_key: str, candidate_key: str
) -> SubstituteEvidence:
    loader = _loader(request)
    try:
        ev = loader.get_evidence()
    except ArtifactMissingError as exc:
        raise _missing("evidence") from exc
    for item in ev.items:
        if item.source_key == source_key and item.candidate_key == candidate_key:
            return item
    raise HTTPException(
        status_code=404,
        detail={
            "error": "evidence_pair_not_found",
            "source_key": source_key,
            "candidate_key": candidate_key,
        },
    )


@router.get("/assessments", response_model=AssessmentReport)
def get_assessments(request: Request) -> AssessmentReport:
    loader = _loader(request)
    try:
        return loader.get_assessments()
    except ArtifactMissingError as exc:
        raise _missing("assessments") from exc


@router.get("/assessments/{row_key}", response_model=SubstituteAssessment)
def get_assessment(request: Request, row_key: str) -> SubstituteAssessment:
    loader = _loader(request)
    try:
        asmt = loader.get_assessments()
    except ArtifactMissingError as exc:
        raise _missing("assessments") from exc
    for item in asmt.items:
        if _row_key(item) == row_key:
            return item
    raise HTTPException(
        status_code=404, detail={"error": "assessment_not_found", "row_key": row_key}
    )


@router.get("/recommendations", response_model=RecommendationReport)
def get_recommendations(request: Request) -> RecommendationReport:
    loader = _loader(request)
    try:
        return loader.get_recommendations()
    except ArtifactMissingError as exc:
        raise _missing("recommendations") from exc


@router.get("/recommendations/{row_key}", response_model=SourcingRecommendation)
def get_recommendation(request: Request, row_key: str) -> SourcingRecommendation:
    loader = _loader(request)
    try:
        rec = loader.get_recommendations()
    except ArtifactMissingError as exc:
        raise _missing("recommendations") from exc
    for item in rec.items:
        if item.row_key() == row_key:
            return item
    raise HTTPException(
        status_code=404, detail={"error": "recommendation_not_found", "row_key": row_key}
    )


@router.get("/opportunities", response_model=list[ConsolidationOpportunity])
def get_opportunities(request: Request) -> list[ConsolidationOpportunity]:
    loader = _loader(request)
    try:
        rec = loader.get_recommendations()
    except ArtifactMissingError as exc:
        raise _missing("recommendations") from exc
    return list(rec.opportunities)


@router.get("/opportunities/{source_key}", response_model=OpportunityDetailOut)
def get_opportunity_detail(request: Request, source_key: str) -> OpportunityDetailOut:
    loader = _loader(request)
    try:
        rec = loader.get_recommendations()
    except ArtifactMissingError as exc:
        raise _missing("recommendations") from exc

    opp = next((o for o in rec.opportunities if o.source_key == source_key), None)
    if opp is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "opportunity_not_found", "source_key": source_key},
        )

    return _build_opportunity_detail(loader, opp, rec)


@router.get("/supply-network", response_model=SupplyNetworkBundle)
def get_supply_network(request: Request) -> SupplyNetworkBundle:
    """Return the full supply-network bundle (nodes + edges + aggregates)."""
    svc = _supply_network_service(request)
    try:
        return svc.get()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail={"error": "supply_network_unavailable", "reason": str(exc)},
        ) from exc


@router.get("/dashboard", response_model=DashboardBundle)
def get_dashboard(request: Request) -> DashboardBundle:
    """One-shot bundle with every artifact needed by the dashboard.

    Missing phases degrade gracefully: the relevant field is ``null`` and the
    phase name appears in ``missing`` so the UI can render empty states.
    """
    loader = _loader(request)
    summary, _, missing = _build_summary(loader)

    registry = _build_registry_bundle(loader)

    try:
        candidates = loader.get_candidates()
    except ArtifactMissingError:
        candidates = None

    try:
        evidence = loader.get_evidence()
    except ArtifactMissingError:
        evidence = None

    try:
        assessments = loader.get_assessments()
    except ArtifactMissingError:
        assessments = None

    try:
        recommendations = loader.get_recommendations()
    except ArtifactMissingError:
        recommendations = None

    opportunity_details: list[OpportunityDetailOut] = []
    if recommendations is not None:
        opportunity_details = [
            _build_opportunity_detail(loader, opp, recommendations)
            for opp in recommendations.opportunities
        ]

    svc = _supply_network_service(request)
    try:
        supply_network = svc.get()
    except FileNotFoundError:
        supply_network = None
        missing.append("supply_network")

    return DashboardBundle(
        summary=summary,
        registry=registry,
        candidates=candidates,
        evidence=evidence,
        assessments=assessments,
        recommendations=recommendations,
        opportunity_details=opportunity_details,
        supply_network=supply_network,
        missing=missing,
    )


__all__ = ["router"]
