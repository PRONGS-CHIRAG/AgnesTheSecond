"""Pure feature extraction for Phase 4 substitute candidates."""

from __future__ import annotations

from agnes.graph.queries import MaterialGraphIndex
from agnes.models.substitutes import CandidateFeatures


def _tokens(canonical_key: str) -> set[str]:
    """Canonical-key token set (hyphen-separated, lowercased, non-empty)."""
    return {tok for tok in canonical_key.lower().split("-") if tok}


def lexical_sim(a: str, b: str) -> float:
    """Jaccard similarity over canonical-key tokens; 0.0 for identical keys."""
    if a == b:
        return 0.0
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    if union == 0:
        return 0.0
    return inter / union


def _jaccard(a: set[int], b: set[int]) -> float:
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    if union == 0:
        return 0.0
    return inter / union


def family_match(
    index: MaterialGraphIndex, source_key: str, candidate_key: str
) -> bool:
    """True if both canonical materials share a (non-None) ``IngredientFamily``."""
    fa = index.family_of(source_key)
    fb = index.family_of(candidate_key)
    return fa is not None and fb is not None and fa == fb


def role_match(
    index: MaterialGraphIndex, source_key: str, candidate_key: str
) -> bool:
    """True if both canonical materials share a (non-None) ``FunctionalRole``."""
    ra = index.role_of(source_key)
    rb = index.role_of(candidate_key)
    return ra is not None and rb is not None and ra == rb


def supplier_overlap(
    index: MaterialGraphIndex, source_key: str, candidate_key: str
) -> float:
    """Jaccard of supplier-id sets between two canonical materials."""
    return _jaccard(
        index.suppliers_for_material(source_key),
        index.suppliers_for_material(candidate_key),
    )


def co_company_overlap(
    index: MaterialGraphIndex, source_key: str, candidate_key: str
) -> float:
    """Jaccard of company-id sets between two canonical materials."""
    return _jaccard(
        index.companies_for_material(source_key),
        index.companies_for_material(candidate_key),
    )


def compute_features(
    index: MaterialGraphIndex,
    source_key: str,
    candidate_key: str,
    *,
    embed_sim: float | None = None,
) -> CandidateFeatures:
    """
    Compute all deterministic signals plus an optional pre-computed ``embed_sim``.

    ``missing_signals`` lists names of signals that could not be evaluated (e.g.
    ``no_family`` when either side lacks a family assignment).
    """
    missing: list[str] = []
    fa = index.family_of(source_key)
    fb = index.family_of(candidate_key)
    if fa is None or fb is None:
        missing.append("family")
    ra = index.role_of(source_key)
    rb = index.role_of(candidate_key)
    if ra is None or rb is None:
        missing.append("role")
    if embed_sim is None:
        missing.append("embed")

    return CandidateFeatures(
        family_match=fa is not None and fb is not None and fa == fb,
        role_match=ra is not None and rb is not None and ra == rb,
        lexical_sim=lexical_sim(source_key, candidate_key),
        embed_sim=embed_sim,
        supplier_overlap=supplier_overlap(index, source_key, candidate_key),
        co_company_overlap=co_company_overlap(index, source_key, candidate_key),
        missing_signals=missing,
    )
