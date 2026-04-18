"""Phase 6 context expansion tests (no DB engine)."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from agnes.models.canonical import (
    CanonicalMaterial,
    CanonicalRegistry,
    RegistryCoverage,
)
from agnes.models.evidence import (
    EvidenceReport,
    SubstituteEvidence,
)
from agnes.reasoning.context import expand_context


def _registry() -> CanonicalRegistry:
    mats = [
        CanonicalMaterial(
            raw_product_id=1,
            sku="RM-1",
            company_id=1,
            normalized_name="calcium citrate",
            canonical_key="calcium-citrate",
            ingredient_family="vitamin_mineral",
            functional_role="active_ingredient",
            confidence=0.9,
            missing_info=[],
            parse_ok=True,
            taxonomy_version="v1",
        ),
        CanonicalMaterial(
            raw_product_id=11,
            sku="RM-11",
            company_id=2,
            normalized_name="calcium citrate",
            canonical_key="calcium-citrate",
            ingredient_family="vitamin_mineral",
            functional_role="active_ingredient",
            confidence=0.85,
            missing_info=[],
            parse_ok=True,
            taxonomy_version="v1",
        ),
        CanonicalMaterial(
            raw_product_id=2,
            sku="RM-2",
            company_id=1,
            normalized_name="magnesium citrate",
            canonical_key="magnesium-citrate",
            ingredient_family="vitamin_mineral",
            functional_role="active_ingredient",
            confidence=0.9,
            missing_info=[],
            parse_ok=True,
            taxonomy_version="v1",
        ),
    ]
    return CanonicalRegistry(
        taxonomy_version="v1",
        generated_at=datetime.now(UTC),
        unique_canonical_keys=2,
        coverage=RegistryCoverage(assigned=3, unassigned=0, parse_failed=0),
        materials=mats,
    )


def _evidence_report() -> EvidenceReport:
    ev = SubstituteEvidence(
        source_key="calcium-citrate",
        candidate_key="magnesium-citrate",
        claims=[],
        n_citations=0,
        any_contradictions=False,
        retrieved_at=datetime.now(UTC),
        llm_model="gpt-4o-mini",
    )
    return EvidenceReport(
        generated_at=datetime.now(UTC),
        llm_model="gpt-4o-mini",
        n_sources=1,
        n_pairs=1,
        n_cache_hits=0,
        n_api_calls=1,
        duration_ms=10,
        items=[ev],
    )


def _tree() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "CompanyId": 1,
                "CompanyName": "Acme",
                "FinishedProductId": 100,
                "FinishedSKU": "ACME-100",
                "RawProductId": 1,
            },
            {
                "CompanyId": 1,
                "CompanyName": "Acme",
                "FinishedProductId": 101,
                "FinishedSKU": "ACME-101",
                "RawProductId": 1,
            },
            {
                "CompanyId": 2,
                "CompanyName": "Beta",
                "FinishedProductId": 200,
                "FinishedSKU": "BETA-200",
                "RawProductId": 11,
            },
        ]
    )


def test_expand_context_fans_out_per_company_product() -> None:
    contexts = expand_context(
        _registry(),
        engine=None,  # type: ignore[arg-type]
        evidence_report=_evidence_report(),
        usage_df=_tree(),
    )
    tuples = [
        (c.company_id, c.finished_product_id, c.source_key, c.candidate_key)
        for c in contexts
    ]
    assert tuples == [
        (1, 100, "calcium-citrate", "magnesium-citrate"),
        (1, 101, "calcium-citrate", "magnesium-citrate"),
        (2, 200, "calcium-citrate", "magnesium-citrate"),
    ]
    assert contexts[0].source_display_name == "calcium citrate"
    assert contexts[0].candidate_display_name == "magnesium citrate"
    assert contexts[0].company_name == "Acme"
    assert contexts[0].finished_product_sku == "ACME-100"


def test_expand_context_skips_missing_usage() -> None:
    """A source canonical_key with zero BOM rows yields no tuples."""
    registry = _registry()
    empty_tree = pd.DataFrame(
        columns=[
            "CompanyId",
            "CompanyName",
            "FinishedProductId",
            "FinishedSKU",
            "RawProductId",
        ]
    )
    contexts = expand_context(
        registry,
        engine=None,  # type: ignore[arg-type]
        evidence_report=_evidence_report(),
        usage_df=empty_tree,
    )
    assert contexts == []


def test_expand_context_dedups_duplicate_rows() -> None:
    tree = _tree()
    tree = pd.concat([tree, tree], ignore_index=True)  # duplicate every row
    contexts = expand_context(
        _registry(),
        engine=None,  # type: ignore[arg-type]
        evidence_report=_evidence_report(),
        usage_df=tree,
    )
    assert len(contexts) == 3


def test_expand_context_sort_order_is_stable() -> None:
    scrambled = _tree().iloc[[2, 0, 1]].reset_index(drop=True)
    contexts = expand_context(
        _registry(),
        engine=None,  # type: ignore[arg-type]
        evidence_report=_evidence_report(),
        usage_df=scrambled,
    )
    keys = [(c.company_id, c.finished_product_id) for c in contexts]
    assert keys == sorted(keys)
