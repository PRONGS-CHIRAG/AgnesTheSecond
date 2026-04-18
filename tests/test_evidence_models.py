"""Schema tests for Phase 5 evidence models."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from agnes.models.evidence import (
    EVIDENCE_SCHEMA_VERSION,
    CitationRef,
    EvidenceClaim,
    EvidenceReport,
    SubstituteEvidence,
    SubstituteEvidenceLLM,
)


def _citation() -> CitationRef:
    return CitationRef(
        url="https://supplier.example.com/magnesium-citrate",
        title="Magnesium Citrate Spec Sheet",
        domain="supplier.example.com",
        retrieved_at=datetime(2026, 4, 18, tzinfo=UTC),
    )


def _claim(key: str = "functional_equivalence") -> EvidenceClaim:
    return EvidenceClaim(
        key=key,
        value=(
            "Magnesium citrate is commonly substituted for calcium citrate "
            "in mineral supplements."
        ),
        polarity="supports",
        confidence=0.72,
        citations=[_citation()],
        grounding_strength="grounded",
    )


def test_citation_round_trip() -> None:
    c = _citation()
    restored = CitationRef.model_validate_json(c.model_dump_json())
    assert restored == c


def test_claim_round_trip_and_frozen() -> None:
    claim = _claim()
    restored = EvidenceClaim.model_validate_json(claim.model_dump_json())
    assert restored == claim
    with pytest.raises(ValidationError):
        claim.__setattr__("confidence", 0.99)


def test_claim_confidence_bounds_enforced() -> None:
    with pytest.raises(ValidationError):
        EvidenceClaim(
            key="functional_equivalence",
            value="x",
            polarity="supports",
            confidence=1.5,
            citations=[],
            grounding_strength="parametric",
        )


def test_claim_rejects_unknown_key() -> None:
    with pytest.raises(ValidationError):
        EvidenceClaim(
            key="not_a_real_key",  # type: ignore[arg-type]
            value="x",
            polarity="supports",
            confidence=0.1,
            citations=[],
            grounding_strength="parametric",
        )


def test_substitute_evidence_extra_forbid() -> None:
    payload = {
        "source_key": "calcium-citrate",
        "candidate_key": "magnesium-citrate",
        "claims": [],
        "n_citations": 0,
        "any_contradictions": False,
        "retrieved_at": "2026-04-18T00:00:00Z",
        "gemini_model": "gemini-2.5-flash",
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "unexpected_field": "boom",
    }
    with pytest.raises(ValidationError):
        SubstituteEvidence.model_validate(payload)


def test_substitute_evidence_llm_is_subset() -> None:
    llm = SubstituteEvidenceLLM(claims=[_claim(), _claim(key="certification")])
    assert len(llm.claims) == 2
    # Roundtrip through JSON mirrors what the grounded backend returns.
    restored = SubstituteEvidenceLLM.model_validate_json(llm.model_dump_json())
    assert restored == llm


def test_evidence_report_defaults_schema_version() -> None:
    report = EvidenceReport(
        generated_at=datetime.now(UTC),
        gemini_model="gemini-2.5-flash",
        n_sources=0,
        n_pairs=0,
        n_cache_hits=0,
        n_api_calls=0,
        duration_ms=0,
    )
    assert report.schema_version == EVIDENCE_SCHEMA_VERSION
    assert report.items == []
