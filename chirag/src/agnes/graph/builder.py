"""Deterministic graph payload builder for Phase 3 (nodes + edges)."""

from __future__ import annotations

from sqlalchemy.engine import Engine

from agnes.canonicalization.taxonomy import FAMILIES, ROLES
from agnes.data.queries import (
    load_companies,
    load_suppliers,
    raw_material_suppliers,
)
from agnes.models.canonical import CanonicalRegistry
from agnes.models.graph import KGEdge, KGNode, node_id


def _mk_node(kind, key, props=None) -> KGNode:
    return KGNode(id=node_id(kind, key), kind=kind, props=props or {})


def build_graph_payload(
    registry: CanonicalRegistry,
    engine: Engine,
    *,
    limit: int | None = None,
) -> tuple[list[KGNode], list[KGEdge]]:
    """
    Build typed ``(nodes, edges)`` lists from ``registry`` + SQLite ``engine``.

    Output is deterministic: all lists are sorted by ``(kind, id)``.
    """
    materials = registry.materials
    if limit is not None:
        materials = materials[:limit]
    raw_ids = {m.raw_product_id for m in materials}
    company_ids = {m.company_id for m in materials}

    companies_df = load_companies(engine)
    companies_df = companies_df[companies_df["Id"].isin(company_ids)]
    suppliers_df = load_suppliers(engine)
    raw_supp_df = raw_material_suppliers(engine)
    raw_supp_df = raw_supp_df[raw_supp_df["ProductId"].isin(raw_ids)]

    needed_supplier_ids: set[int] = set()
    for _, row in raw_supp_df.iterrows():
        for sid in row["supplier_ids"]:
            needed_supplier_ids.add(int(sid))
    suppliers_df = suppliers_df[suppliers_df["Id"].isin(needed_supplier_ids)]

    nodes: list[KGNode] = []
    edges: list[KGEdge] = []

    for _, row in companies_df.iterrows():
        nodes.append(_mk_node("Company", int(row["Id"]), {"name": str(row["Name"])}))
    for _, row in suppliers_df.iterrows():
        nodes.append(_mk_node("Supplier", int(row["Id"]), {"name": str(row["Name"])}))

    assigned_families: set[str] = set()
    assigned_roles: set[str] = set()
    emitted_canonical: set[str] = set()

    for m in materials:
        nodes.append(
            _mk_node(
                "RawProduct",
                m.raw_product_id,
                {
                    "sku": m.sku,
                    "normalized_name": m.normalized_name,
                    "company_id": m.company_id,
                    "canonical_key": m.canonical_key,
                },
            )
        )
        if m.canonical_key not in emitted_canonical:
            nodes.append(
                _mk_node(
                    "CanonicalMaterial",
                    m.canonical_key,
                    {
                        "canonical_key": m.canonical_key,
                        "normalized_name": m.normalized_name,
                        "ingredient_family": m.ingredient_family,
                        "functional_role": m.functional_role,
                        "confidence": m.confidence,
                        "taxonomy_version": m.taxonomy_version,
                    },
                )
            )
            emitted_canonical.add(m.canonical_key)
        if m.ingredient_family and m.ingredient_family != "other":
            assigned_families.add(m.ingredient_family)
        if m.functional_role and m.functional_role != "other":
            assigned_roles.add(m.functional_role)

    for fam in sorted(set(FAMILIES)):
        nodes.append(_mk_node("IngredientFamily", fam, {"name": fam}))
    for role in sorted(set(ROLES)):
        nodes.append(_mk_node("FunctionalRole", role, {"name": role}))

    for m in materials:
        edges.append(
            KGEdge(
                source=node_id("Company", m.company_id),
                target=node_id("RawProduct", m.raw_product_id),
                kind="OWNS",
            )
        )
        edges.append(
            KGEdge(
                source=node_id("RawProduct", m.raw_product_id),
                target=node_id("CanonicalMaterial", m.canonical_key),
                kind="INSTANCE_OF",
            )
        )
        edges.append(
            KGEdge(
                source=node_id("RawProduct", m.raw_product_id),
                target=node_id("Company", m.company_id),
                kind="USED_BY",
            )
        )

    emitted_family_edges: set[tuple[str, str]] = set()
    emitted_role_edges: set[tuple[str, str]] = set()
    for m in materials:
        if m.ingredient_family and m.ingredient_family != "other":
            edge = (m.canonical_key, m.ingredient_family)
            if edge not in emitted_family_edges:
                edges.append(
                    KGEdge(
                        source=node_id("CanonicalMaterial", m.canonical_key),
                        target=node_id("IngredientFamily", m.ingredient_family),
                        kind="BELONGS_TO_FAMILY",
                    )
                )
                emitted_family_edges.add(edge)
        if m.functional_role and m.functional_role != "other":
            edge = (m.canonical_key, m.functional_role)
            if edge not in emitted_role_edges:
                edges.append(
                    KGEdge(
                        source=node_id("CanonicalMaterial", m.canonical_key),
                        target=node_id("FunctionalRole", m.functional_role),
                        kind="HAS_ROLE",
                    )
                )
                emitted_role_edges.add(edge)

    for _, row in raw_supp_df.iterrows():
        raw_id = int(row["ProductId"])
        for sid in row["supplier_ids"]:
            edges.append(
                KGEdge(
                    source=node_id("Supplier", int(sid)),
                    target=node_id("RawProduct", raw_id),
                    kind="OFFERS",
                )
            )

    nodes_sorted = sorted(nodes, key=lambda n: (n.kind, n.id))
    edges_sorted = sorted(edges, key=lambda e: (e.kind, e.source, e.target))
    return nodes_sorted, edges_sorted


def count_by_kind(
    nodes: list[KGNode], edges: list[KGEdge]
) -> tuple[dict[str, int], dict[str, int]]:
    """Return ``(node_counts_by_kind, edge_counts_by_kind)`` dicts."""
    nc: dict[str, int] = {}
    for n in nodes:
        nc[n.kind] = nc.get(n.kind, 0) + 1
    ec: dict[str, int] = {}
    for e in edges:
        ec[e.kind] = ec.get(e.kind, 0) + 1
    return nc, ec
