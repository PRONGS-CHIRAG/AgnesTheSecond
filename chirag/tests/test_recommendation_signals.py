"""Phase 7 structural sourcing-signal unit tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from agnes.models.canonical import (
    CanonicalMaterial,
    CanonicalRegistry,
    RegistryCoverage,
)
from agnes.recommendation.signals import build_supplier_index, compute_signals


def _material(raw_id: int, key: str, company_id: int = 1) -> CanonicalMaterial:
    return CanonicalMaterial(
        raw_product_id=raw_id,
        sku=f"SKU-{raw_id}",
        company_id=company_id,
        normalized_name=key.replace("-", " "),
        canonical_key=key,
        ingredient_family="citrates",
        functional_role="chelator",
        confidence=0.9,
        parse_ok=True,
        taxonomy_version="v1",
    )


def _registry(*materials: CanonicalMaterial) -> CanonicalRegistry:
    return CanonicalRegistry(
        taxonomy_version="v1",
        generated_at=datetime.now(UTC),
        unique_canonical_keys=len({m.canonical_key for m in materials}),
        coverage=RegistryCoverage(assigned=len(materials), unassigned=0, parse_failed=0),
        materials=list(materials),
    )


def _suppliers_df(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(
            columns=["ProductId", "SKU", "supplier_count", "supplier_ids", "supplier_names"]
        )
    return pd.DataFrame(rows)


def _company_df(pairs: list[tuple[int, int]]) -> pd.DataFrame:
    if not pairs:
        return pd.DataFrame(columns=["CompanyId", "SupplierId", "RawProductId"])
    return pd.DataFrame(
        [
            {"CompanyId": c, "SupplierId": s, "RawProductId": 0}
            for c, s in pairs
        ]
    )


def test_build_supplier_index_groups_raw_ids_by_key() -> None:
    registry = _registry(
        _material(101, "calcium-citrate"),
        _material(102, "calcium-citrate"),
        _material(201, "magnesium-citrate"),
    )
    suppliers = _suppliers_df(
        [
            {
                "ProductId": 101,
                "SKU": "S-101",
                "supplier_count": 1,
                "supplier_ids": [1],
                "supplier_names": ["Alpha"],
            },
            {
                "ProductId": 102,
                "SKU": "S-102",
                "supplier_count": 1,
                "supplier_ids": [2],
                "supplier_names": ["Beta"],
            },
            {
                "ProductId": 201,
                "SKU": "S-201",
                "supplier_count": 2,
                "supplier_ids": [2, 3],
                "supplier_names": ["Beta", "Gamma"],
            },
        ]
    )
    index = build_supplier_index(registry, suppliers, _company_df([(1, 2)]))
    assert index.suppliers_by_key["calcium-citrate"] == {1, 2}
    assert index.suppliers_by_key["magnesium-citrate"] == {2, 3}
    assert index.supplier_names_by_key["calcium-citrate"] == ["Alpha", "Beta"]
    assert index.suppliers_by_company[1] == {2}


def test_concentration_relief_requires_source_le_1_and_candidate_ge_2() -> None:
    registry = _registry(
        _material(101, "calcium-citrate"),
        _material(201, "magnesium-citrate"),
    )
    suppliers = _suppliers_df(
        [
            {
                "ProductId": 101,
                "SKU": "S-101",
                "supplier_count": 1,
                "supplier_ids": [1],
                "supplier_names": ["Alpha"],
            },
            {
                "ProductId": 201,
                "SKU": "S-201",
                "supplier_count": 2,
                "supplier_ids": [2, 3],
                "supplier_names": ["Beta", "Gamma"],
            },
        ]
    )
    index = build_supplier_index(registry, suppliers, _company_df([]))
    signals = compute_signals(
        index,
        company_id=1,
        source_key="calcium-citrate",
        candidate_key="magnesium-citrate",
    )
    assert signals.concentration_relief == 1.0
    assert signals.source_supplier_count == 1
    assert signals.candidate_supplier_count == 2

    signals_back = compute_signals(
        index,
        company_id=1,
        source_key="magnesium-citrate",
        candidate_key="calcium-citrate",
    )
    assert signals_back.concentration_relief == 0.0


def test_company_overlap_ratio() -> None:
    registry = _registry(
        _material(101, "calcium-citrate"),
        _material(201, "magnesium-citrate"),
    )
    suppliers = _suppliers_df(
        [
            {
                "ProductId": 101,
                "SKU": "S-101",
                "supplier_count": 1,
                "supplier_ids": [1],
                "supplier_names": ["Alpha"],
            },
            {
                "ProductId": 201,
                "SKU": "S-201",
                "supplier_count": 2,
                "supplier_ids": [2, 3],
                "supplier_names": ["Beta", "Gamma"],
            },
        ]
    )
    index = build_supplier_index(registry, suppliers, _company_df([(7, 2)]))
    signals = compute_signals(
        index,
        company_id=7,
        source_key="calcium-citrate",
        candidate_key="magnesium-citrate",
    )
    assert signals.company_supplier_overlap == 0.5
    assert 2 in set(index.suppliers_by_company[7])


def test_missing_signals_when_no_supplier_data() -> None:
    registry = _registry(
        _material(101, "calcium-citrate"),
        _material(201, "magnesium-citrate"),
    )
    suppliers = _suppliers_df([])
    index = build_supplier_index(registry, suppliers, _company_df([]))
    signals = compute_signals(
        index,
        company_id=1,
        source_key="calcium-citrate",
        candidate_key="magnesium-citrate",
    )
    assert signals.missing_signals == ["no_supplier_data"]
    assert signals.company_supplier_overlap == 0.0
    assert signals.concentration_relief == 0.0
