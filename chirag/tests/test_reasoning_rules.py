"""Unit tests for the Phase 6 deterministic scorer."""

from __future__ import annotations

from datetime import UTC, datetime

from agnes.models.evidence import (
    CitationRef,
    EvidenceClaim,
    SubstituteEvidence,
)
from agnes.reasoning.rules import (
    DEFAULT_CLAIM_WEIGHTS,
    RulesConfig,
    aggregate_claims,
    classify,
    score_acceptability,
)


def _cite() -> CitationRef:
    return CitationRef(
        url="https://example.com/doc",
        title="Doc",
        domain="example.com",
        retrieved_at=datetime(2026, 4, 18, tzinfo=UTC),
    )


def _evidence(*claims: EvidenceClaim, contradictions: bool = False) -> SubstituteEvidence:
    return SubstituteEvidence(
        source_key="calcium-citrate",
        candidate_key="magnesium-citrate",
        claims=list(claims),
        n_citations=sum(len(c.citations) for c in claims),
        any_contradictions=contradictions,
        retrieved_at=datetime.now(UTC),
        llm_model="gpt-4o-mini",
    )


def _claim(
    key: str,
    *,
    polarity: str = "supports",
    confidence: float = 0.8,
    grounded: bool = True,
) -> EvidenceClaim:
    return EvidenceClaim(
        key=key,  # type: ignore[arg-type]
        value="...",
        polarity=polarity,  # type: ignore[arg-type]
        confidence=confidence,
        citations=[_cite()] if grounded else [],
        grounding_strength="grounded" if grounded else "parametric",
    )


def test_aggregate_claims_counts_citations_and_missing() -> None:
    ev = _evidence(
        _claim("functional_equivalence", confidence=0.9),
        _claim("regulatory", polarity="contradicts", confidence=0.7),
    )
    agg = aggregate_claims(ev)
    assert agg.total_claims == 2
    assert agg.grounded_claims == 2
    assert agg.contradictions == ["regulatory"]
    assert "certification" in agg.missing_information
    assert len(agg.citations) == 1
    assert agg.any_high_weight_contradiction is True


def test_score_acceptability_monotonic_in_support() -> None:
    cfg = RulesConfig(claim_weights=dict(DEFAULT_CLAIM_WEIGHTS))
    weak = aggregate_claims(
        _evidence(_claim("functional_equivalence", confidence=0.3))
    )
    strong = aggregate_claims(
        _evidence(_claim("functional_equivalence", confidence=0.95))
    )
    assert score_acceptability(strong, cfg) > score_acceptability(weak, cfg)


def test_score_acceptability_penalized_by_contradiction() -> None:
    cfg = RulesConfig(claim_weights=dict(DEFAULT_CLAIM_WEIGHTS))
    supports = aggregate_claims(
        _evidence(_claim("functional_equivalence", confidence=0.9))
    )
    mixed = aggregate_claims(
        _evidence(
            _claim("functional_equivalence", confidence=0.9),
            _claim("functional_equivalence", polarity="contradicts", confidence=0.8),
        )
    )
    assert score_acceptability(supports, cfg) > score_acceptability(mixed, cfg)


def test_classify_recommend_thresholds() -> None:
    cfg = RulesConfig(
        claim_weights=dict(DEFAULT_CLAIM_WEIGHTS),
        accept_threshold=0.75,
        reject_threshold=0.35,
        min_grounded_claims=2,
    )
    agg = aggregate_claims(
        _evidence(
            _claim("functional_equivalence", confidence=1.0),
            _claim("regulatory", confidence=1.0),
            _claim("certification", confidence=1.0),
            _claim("quality_sensory", confidence=1.0),
            _claim("price_availability", confidence=1.0),
            _claim("typical_suppliers", confidence=1.0),
        )
    )
    acc = score_acceptability(agg, cfg)
    cls, borderline = classify(acc, agg, cfg)
    assert acc >= 0.75
    assert cls == "recommend"
    assert borderline is False


def test_classify_do_not_recommend() -> None:
    cfg = RulesConfig(
        claim_weights=dict(DEFAULT_CLAIM_WEIGHTS),
        accept_threshold=0.75,
        reject_threshold=0.35,
        min_grounded_claims=2,
    )
    agg = aggregate_claims(
        _evidence(
            _claim("functional_equivalence", polarity="contradicts", confidence=0.95),
            _claim("regulatory", polarity="contradicts", confidence=0.9),
        )
    )
    acc = score_acceptability(agg, cfg)
    cls, borderline = classify(acc, agg, cfg)
    assert cls == "do_not_recommend"
    assert borderline is True  # high-weight contradictions


def test_classify_insufficient_evidence() -> None:
    cfg = RulesConfig(
        claim_weights=dict(DEFAULT_CLAIM_WEIGHTS),
        min_grounded_claims=2,
    )
    agg = aggregate_claims(
        _evidence(_claim("functional_equivalence", confidence=0.8))
    )
    cls, borderline = classify(0.9, agg, cfg)
    assert cls == "insufficient_evidence"
    assert borderline is False


def test_classify_borderline_flagged_on_with_caveats() -> None:
    cfg = RulesConfig(
        claim_weights=dict(DEFAULT_CLAIM_WEIGHTS),
        accept_threshold=0.80,
        reject_threshold=0.35,
        min_grounded_claims=2,
    )
    agg = aggregate_claims(
        _evidence(
            _claim("functional_equivalence", confidence=0.7),
            _claim("price_availability", confidence=0.6),
        )
    )
    acc = score_acceptability(agg, cfg)
    cls, borderline = classify(acc, agg, cfg)
    assert cls == "recommend_with_caveats"
    assert borderline is True
