"""
Phase 6 deterministic claim-aggregation rules.

Pure functions only: inputs in, decision out. No I/O, no LLM, no clock.
Everything here is driven by ``RulesConfig`` so demo tuning stays in settings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import get_args

from agnes.models.assessment import RecommendationClass
from agnes.models.evidence import (
    CitationRef,
    ClaimKey,
    EvidenceClaim,
    SubstituteEvidence,
)

DEFAULT_CLAIM_WEIGHTS: dict[str, float] = {
    "functional_equivalence": 0.35,
    "regulatory": 0.25,
    "certification": 0.15,
    "quality_sensory": 0.10,
    "price_availability": 0.10,
    "typical_suppliers": 0.05,
}

HIGH_WEIGHT_KEYS: frozenset[str] = frozenset(
    {"functional_equivalence", "regulatory", "certification"}
)

ALL_CLAIM_KEYS: tuple[str, ...] = tuple(get_args(ClaimKey))


@dataclass(frozen=True)
class RulesConfig:
    """Tunable knobs for the deterministic scorer."""

    claim_weights: dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_CLAIM_WEIGHTS)
    )
    accept_threshold: float = 0.75
    reject_threshold: float = 0.35
    min_grounded_claims: int = 2

    def weight(self, key: str) -> float:
        return self.claim_weights.get(key, 0.0)


@dataclass(frozen=True)
class ClaimAggregate:
    """Per-pair aggregation of evidence claims, keyed by claim key."""

    per_key_support: dict[str, float]
    per_key_contradict: dict[str, float]
    per_key_polarity: dict[str, str]
    grounded_claims: int
    total_claims: int
    contradictions: list[str]
    missing_information: list[str]
    citations: list[CitationRef]

    @property
    def any_high_weight_contradiction(self) -> bool:
        return any(k in HIGH_WEIGHT_KEYS for k in self.contradictions)

    @property
    def missing_regulatory_or_certification(self) -> bool:
        return any(
            k in {"regulatory", "certification"} for k in self.missing_information
        )


def _weight_polarity(polarity: str) -> tuple[float, float]:
    """Return ``(support_factor, contradict_factor)`` for a polarity string."""
    if polarity == "supports":
        return 1.0, 0.0
    if polarity == "contradicts":
        return 0.0, 1.0
    if polarity == "mixed":
        return 0.5, 0.5
    return 0.0, 0.0


def _grounding_multiplier(claim: EvidenceClaim) -> float:
    """Favor claims backed by citations. Parametric claims count half."""
    if claim.grounding_strength == "grounded" and claim.citations:
        return 1.0
    if claim.grounding_strength == "grounded":
        return 0.75
    return 0.5


def aggregate_claims(evidence: SubstituteEvidence) -> ClaimAggregate:
    """
    Collapse a list of ``EvidenceClaim`` into per-key support/contradict scores.

    Per claim contribution is ``confidence * grounding_multiplier * polarity_factor``.
    Multiple claims on the same key accumulate (additive), then are clipped to ``[0, 1]``
    inside :func:`score_acceptability` when combined with weights.
    """
    per_support: dict[str, float] = {k: 0.0 for k in ALL_CLAIM_KEYS}
    per_contradict: dict[str, float] = {k: 0.0 for k in ALL_CLAIM_KEYS}
    per_polarity: dict[str, str] = {}

    grounded = 0
    total = 0
    citations: list[CitationRef] = []
    seen_urls: set[str] = set()
    contradictions: list[str] = []
    keys_seen: set[str] = set()

    for claim in evidence.claims:
        total += 1
        keys_seen.add(claim.key)
        mult = _grounding_multiplier(claim)
        sup_f, con_f = _weight_polarity(claim.polarity)
        weight = claim.confidence * mult
        per_support[claim.key] = min(1.0, per_support[claim.key] + sup_f * weight)
        per_contradict[claim.key] = min(
            1.0, per_contradict[claim.key] + con_f * weight
        )
        if claim.grounding_strength == "grounded" and claim.citations:
            grounded += 1
        if claim.polarity in {"contradicts", "mixed"} and con_f > 0:
            if claim.key not in contradictions:
                contradictions.append(claim.key)
        per_polarity[claim.key] = claim.polarity
        for cite in claim.citations:
            if cite.url in seen_urls:
                continue
            seen_urls.add(cite.url)
            citations.append(cite)

    missing = [k for k in ALL_CLAIM_KEYS if k not in keys_seen]
    return ClaimAggregate(
        per_key_support=per_support,
        per_key_contradict=per_contradict,
        per_key_polarity=per_polarity,
        grounded_claims=grounded,
        total_claims=total,
        contradictions=contradictions,
        missing_information=missing,
        citations=citations,
    )


def score_acceptability(agg: ClaimAggregate, config: RulesConfig) -> float:
    """
    Produce a deterministic acceptability score in ``[0, 1]``.

    The score is the claim-key-weighted sum of ``(support - contradict)`` clamped to
    ``[0, 1]`` per key, then renormalized by the sum of weights actually observed.
    Missing keys contribute nothing (they don't penalize — they're captured separately
    via ``missing_information``).
    """
    total_weight = 0.0
    weighted_sum = 0.0
    for key in ALL_CLAIM_KEYS:
        w = config.weight(key)
        if w <= 0:
            continue
        sup = agg.per_key_support.get(key, 0.0)
        con = agg.per_key_contradict.get(key, 0.0)
        if sup == 0.0 and con == 0.0:
            continue
        net = max(0.0, min(1.0, sup - con))
        weighted_sum += w * net
        total_weight += w
    if total_weight <= 0:
        return 0.0
    return max(0.0, min(1.0, weighted_sum / total_weight))


def classify(
    acceptability: float,
    agg: ClaimAggregate,
    config: RulesConfig,
) -> tuple[RecommendationClass, bool]:
    """
    Map ``acceptability`` + aggregate shape to a :class:`RecommendationClass`.

    Returns ``(recommendation, is_borderline)``. ``is_borderline`` signals that
    the LLM fallback should take a second look.
    """
    if agg.grounded_claims < config.min_grounded_claims:
        return "insufficient_evidence", False

    if acceptability >= config.accept_threshold:
        cls: RecommendationClass = "recommend"
    elif acceptability <= config.reject_threshold:
        cls = "do_not_recommend"
    else:
        cls = "recommend_with_caveats"

    borderline = (
        cls == "recommend_with_caveats"
        or agg.any_high_weight_contradiction
        or agg.missing_regulatory_or_certification
    )
    return cls, borderline


def deterministic_rationale(
    cls: RecommendationClass,
    acceptability: float,
    agg: ClaimAggregate,
) -> str:
    """Short human-readable one-liner for the rules decision path."""
    contr = ", ".join(agg.contradictions) if agg.contradictions else "none"
    miss_short = (
        ", ".join(agg.missing_information[:3])
        if agg.missing_information
        else "none"
    )
    return (
        f"{cls} at acceptability={acceptability:.2f} "
        f"(grounded={agg.grounded_claims}/{agg.total_claims}, "
        f"contradictions={contr}, missing={miss_short})"
    )
