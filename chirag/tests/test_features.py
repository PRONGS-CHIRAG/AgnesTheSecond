"""Unit tests for Phase 4 feature extraction."""

from __future__ import annotations

from agnes.graph.queries import MaterialGraphIndex
from agnes.models.graph import KGEdge, KGNode, node_id
from agnes.substitutes.features import (
    co_company_overlap,
    compute_features,
    family_match,
    lexical_sim,
    role_match,
    supplier_overlap,
)


def _cm(key: str) -> KGNode:
    return KGNode(id=node_id("CanonicalMaterial", key), kind="CanonicalMaterial")


def _fam(name: str) -> KGNode:
    return KGNode(id=node_id("IngredientFamily", name), kind="IngredientFamily")


def _role(name: str) -> KGNode:
    return KGNode(id=node_id("FunctionalRole", name), kind="FunctionalRole")


def _instance_of(raw_id: int, key: str) -> KGEdge:
    return KGEdge(
        source=node_id("RawProduct", raw_id),
        target=node_id("CanonicalMaterial", key),
        kind="INSTANCE_OF",
    )


def _belongs_to(key: str, family: str) -> KGEdge:
    return KGEdge(
        source=node_id("CanonicalMaterial", key),
        target=node_id("IngredientFamily", family),
        kind="BELONGS_TO_FAMILY",
    )


def _has_role(key: str, role: str) -> KGEdge:
    return KGEdge(
        source=node_id("CanonicalMaterial", key),
        target=node_id("FunctionalRole", role),
        kind="HAS_ROLE",
    )


def _owns(company_id: int, raw_id: int) -> KGEdge:
    return KGEdge(
        source=node_id("Company", company_id),
        target=node_id("RawProduct", raw_id),
        kind="OWNS",
    )


def _offers(supplier_id: int, raw_id: int) -> KGEdge:
    return KGEdge(
        source=node_id("Supplier", supplier_id),
        target=node_id("RawProduct", raw_id),
        kind="OFFERS",
    )


def _mini_index() -> MaterialGraphIndex:
    nodes: list[KGNode] = [
        _cm("calcium-citrate"),
        _cm("calcium-lactate"),
        _cm("sodium-citrate"),
        _fam("vitamin_mineral"),
        _fam("acidulant"),
        _role("active_ingredient"),
        KGNode(id=node_id("RawProduct", 1), kind="RawProduct"),
        KGNode(id=node_id("RawProduct", 2), kind="RawProduct"),
        KGNode(id=node_id("RawProduct", 3), kind="RawProduct"),
        KGNode(id=node_id("Company", 1), kind="Company"),
        KGNode(id=node_id("Company", 2), kind="Company"),
        KGNode(id=node_id("Supplier", 1), kind="Supplier"),
        KGNode(id=node_id("Supplier", 2), kind="Supplier"),
    ]
    edges: list[KGEdge] = [
        _instance_of(1, "calcium-citrate"),
        _instance_of(2, "calcium-lactate"),
        _instance_of(3, "sodium-citrate"),
        _belongs_to("calcium-citrate", "vitamin_mineral"),
        _belongs_to("calcium-lactate", "vitamin_mineral"),
        _belongs_to("sodium-citrate", "acidulant"),
        _has_role("calcium-citrate", "active_ingredient"),
        _has_role("calcium-lactate", "active_ingredient"),
        _owns(1, 1),
        _owns(2, 2),
        _owns(1, 3),
        _offers(1, 1),
        _offers(2, 1),
        _offers(1, 2),
        _offers(2, 3),
    ]
    return MaterialGraphIndex.from_payload(nodes, edges)


def test_lexical_sim_shared_tokens() -> None:
    assert lexical_sim("calcium-citrate", "calcium-lactate") == 1 / 3
    assert lexical_sim("calcium-citrate", "calcium-citrate") == 0.0
    assert lexical_sim("", "calcium") == 0.0


def test_family_and_role_match() -> None:
    idx = _mini_index()
    assert family_match(idx, "calcium-citrate", "calcium-lactate") is True
    assert family_match(idx, "calcium-citrate", "sodium-citrate") is False
    assert role_match(idx, "calcium-citrate", "calcium-lactate") is True


def test_supplier_and_company_overlap() -> None:
    idx = _mini_index()
    assert supplier_overlap(idx, "calcium-citrate", "calcium-lactate") == 1 / 2
    assert co_company_overlap(idx, "calcium-citrate", "calcium-lactate") == 0.0
    assert co_company_overlap(idx, "calcium-citrate", "sodium-citrate") == 1.0


def test_compute_features_records_missing_signals() -> None:
    idx = _mini_index()
    f = compute_features(idx, "calcium-citrate", "calcium-lactate")
    assert f.family_match is True
    assert f.role_match is True
    assert f.embed_sim is None
    assert "embed" in f.missing_signals

    f2 = compute_features(idx, "calcium-citrate", "calcium-lactate", embed_sim=0.9)
    assert f2.embed_sim == 0.9
    assert "embed" not in f2.missing_signals
