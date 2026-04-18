"""Weighted composite scoring for Phase 4 substitute candidates."""

from __future__ import annotations

from typing import Final

from agnes.models.substitutes import CandidateFeatures

DEFAULT_WEIGHTS: Final[dict[str, float]] = {
    "family": 0.30,
    "role": 0.15,
    "embed": 0.35,
    "lexical": 0.10,
    "supplier_overlap": 0.10,
}

MISSING_SIGNAL_PENALTY: Final[float] = 0.05


def normalize_weights(weights: dict[str, float] | None) -> dict[str, float]:
    """
    Return a dict with all expected keys; missing keys fall back to defaults.

    Weights are not re-normalized to sum to 1 (so users can tune emphasis), but
    the final ``score_candidate`` output is clamped to ``[0, 1]``.
    """
    if weights is None:
        return dict(DEFAULT_WEIGHTS)
    merged = dict(DEFAULT_WEIGHTS)
    for k, v in weights.items():
        if k in merged:
            merged[k] = float(v)
    return merged


def score_candidate(
    features: CandidateFeatures, weights: dict[str, float] | None = None
) -> float:
    """
    Weighted sum in ``[0, 1]`` over per-signal features.

    Missing signals (``features.missing_signals``) subtract a small penalty per
    entry so candidates with more evidence rank above ones with gaps.
    """
    w = normalize_weights(weights)
    embed = features.embed_sim if features.embed_sim is not None else 0.0
    raw = (
        w["family"] * (1.0 if features.family_match else 0.0)
        + w["role"] * (1.0 if features.role_match else 0.0)
        + w["embed"] * embed
        + w["lexical"] * features.lexical_sim
        + w["supplier_overlap"] * features.supplier_overlap
    )
    penalty = MISSING_SIGNAL_PENALTY * len(features.missing_signals)
    return max(0.0, min(1.0, raw - penalty))
