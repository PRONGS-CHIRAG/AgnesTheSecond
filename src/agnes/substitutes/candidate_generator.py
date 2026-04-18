"""Substitute candidate generation using graph + lexical + embedding signals."""

from __future__ import annotations

import time

import structlog

from agnes.canonicalization.taxonomy import TAXONOMY_VERSION
from agnes.graph.queries import MaterialGraphIndex
from agnes.graph.schema import GRAPH_SCHEMA_VERSION
from agnes.models.canonical import CanonicalRegistry
from agnes.models.substitutes import (
    SubstituteCandidate,
    TargetDiagnostics,
)
from agnes.substitutes.embeddings import EmbeddingClient, cosine
from agnes.substitutes.features import compute_features
from agnes.substitutes.scoring import DEFAULT_WEIGHTS, normalize_weights, score_candidate

logger = structlog.get_logger(__name__)


def _display_text_for(registry_by_key, key: str) -> str:
    """Prefer the first normalized name seen for ``key`` in the registry."""
    mats = registry_by_key.get(key, [])
    if mats:
        return mats[0].normalized_name or key.replace("-", " ")
    return key.replace("-", " ")


def _candidate_pool(
    index: MaterialGraphIndex,
    source_key: str,
    *,
    cross_family: bool,
) -> tuple[list[str], str | None]:
    """
    Return ``(pool, empty_reason)``.

    Pool excludes the source itself. When ``cross_family`` is False the pool is
    the source's family only; when True it's every other canonical material.
    """
    all_keys = set(index.canonical_keys())
    all_keys.discard(source_key)
    if cross_family:
        return sorted(all_keys), None
    fam = index.family_of(source_key)
    if fam is None:
        return [], "no_family"
    siblings = [k for k in index.materials_in_family(fam) if k != source_key]
    if not siblings:
        return [], "singleton_family"
    return sorted(siblings), None


def generate_candidates(
    *,
    target_key: str,
    registry: CanonicalRegistry,
    graph_index: MaterialGraphIndex,
    embeddings: EmbeddingClient | None,
    top_k: int = 10,
    min_score: float = 0.55,
    cross_family: bool = False,
    weights: dict[str, float] | None = None,
) -> tuple[list[SubstituteCandidate], TargetDiagnostics]:
    """
    Generate ranked substitute candidates for ``target_key``.

    Returns ``(candidates, diagnostics)``. When ``embeddings`` is ``None`` the
    embedding signal is skipped (``embed_sim = None``).
    """
    t0 = time.perf_counter()
    reg_by_key = registry.by_canonical_key()
    resolved_weights = normalize_weights(weights)

    logger.debug("phase4_target_start", source_key=target_key, cross_family=cross_family)
    pool, empty_reason = _candidate_pool(
        graph_index, target_key, cross_family=cross_family
    )
    n_pool = len(pool)
    logger.debug(
        "phase4_pool_filtered",
        source_key=target_key,
        n_pool=n_pool,
        family=graph_index.family_of(target_key),
    )
    if not pool:
        diag = TargetDiagnostics(
            source_key=target_key,
            n_pool=0,
            n_after_filter=0,
            n_returned=0,
            reason=empty_reason,
        )
        logger.info(
            "phase4_target_empty",
            source_key=target_key,
            reason=empty_reason,
            elapsed_ms=int((time.perf_counter() - t0) * 1000),
        )
        return [], diag

    embed_sim_by_key: dict[str, float | None] = {k: None for k in pool}
    embedding_model_used: str | None = None
    if embeddings is not None:
        items = [
            (k, _display_text_for(reg_by_key, k))
            for k in [target_key, *pool]
        ]
        vecs = embeddings.get_batch(items)
        embedding_model_used = embeddings.model
        target_vec = vecs.get(target_key)
        if target_vec is not None:
            for k in pool:
                v = vecs.get(k)
                if v is not None:
                    embed_sim_by_key[k] = cosine(target_vec, v)

    scored: list[SubstituteCandidate] = []
    for cand in pool:
        feats = compute_features(
            graph_index,
            target_key,
            cand,
            embed_sim=embed_sim_by_key[cand],
        )
        score = score_candidate(feats, resolved_weights)
        if score < min_score:
            continue
        fam = graph_index.family_of(cand)
        role = graph_index.role_of(cand)
        scored.append(
            SubstituteCandidate(
                source_key=target_key,
                candidate_key=cand,
                family=fam,
                roles=[role] if role else [],
                score=round(score, 6),
                features=feats,
                embedding_model=embedding_model_used,
                taxonomy_version=TAXONOMY_VERSION,
                graph_schema_version=GRAPH_SCHEMA_VERSION,
            )
        )

    scored.sort(key=lambda c: (-c.score, c.candidate_key))
    top = scored[:top_k]

    diag = TargetDiagnostics(
        source_key=target_key,
        n_pool=n_pool,
        n_after_filter=len(scored),
        n_returned=len(top),
        best_score=top[0].score if top else None,
        reason=None if top else "all_below_threshold",
    )

    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    if top:
        logger.info(
            "phase4_target_ok",
            source_key=target_key,
            n_pool=n_pool,
            n_returned=len(top),
            best_score=top[0].score,
            elapsed_ms=elapsed_ms,
        )
    else:
        logger.info(
            "phase4_target_empty",
            source_key=target_key,
            reason="all_below_threshold",
            n_pool=n_pool,
            elapsed_ms=elapsed_ms,
        )
    return top, diag


__all__ = [
    "DEFAULT_WEIGHTS",
    "generate_candidates",
]
