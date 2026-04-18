"""In-memory ``MaterialGraphIndex`` over Phase 3 nodes/edges (no Cognee read path)."""

from __future__ import annotations

from dataclasses import dataclass, field

from agnes.models.graph import KGEdge, KGNode, node_id


@dataclass
class MaterialGraphIndex:
    """
    Pure-Python adjacency index built from a ``(nodes, edges)`` payload.

    Provides the lookups Phase 4 needs without round-tripping through Cognee.
    """

    nodes_by_id: dict[str, KGNode] = field(default_factory=dict)
    nodes_by_kind: dict[str, list[KGNode]] = field(default_factory=dict)
    edges: list[KGEdge] = field(default_factory=list)
    # Core adjacency maps, keyed by node id.
    suppliers_by_raw: dict[str, set[str]] = field(default_factory=dict)
    owner_by_raw: dict[str, str] = field(default_factory=dict)
    raws_by_canonical: dict[str, set[str]] = field(default_factory=dict)
    family_by_canonical: dict[str, str] = field(default_factory=dict)
    role_by_canonical: dict[str, str] = field(default_factory=dict)
    canonicals_by_family: dict[str, set[str]] = field(default_factory=dict)
    canonicals_by_role: dict[str, set[str]] = field(default_factory=dict)

    @classmethod
    def from_payload(
        cls, nodes: list[KGNode], edges: list[KGEdge]
    ) -> MaterialGraphIndex:
        """Build an index from the output of ``build_graph_payload``."""
        idx = cls()
        for n in nodes:
            idx.nodes_by_id[n.id] = n
            idx.nodes_by_kind.setdefault(n.kind, []).append(n)
        idx.edges = list(edges)
        for e in edges:
            if e.kind == "OFFERS":
                idx.suppliers_by_raw.setdefault(e.target, set()).add(e.source)
            elif e.kind == "OWNS":
                idx.owner_by_raw[e.target] = e.source
            elif e.kind == "INSTANCE_OF":
                idx.raws_by_canonical.setdefault(e.target, set()).add(e.source)
            elif e.kind == "BELONGS_TO_FAMILY":
                idx.family_by_canonical[e.source] = e.target
                idx.canonicals_by_family.setdefault(e.target, set()).add(e.source)
            elif e.kind == "HAS_ROLE":
                idx.role_by_canonical[e.source] = e.target
                idx.canonicals_by_role.setdefault(e.target, set()).add(e.source)
        return idx

    def canonical_id(self, canonical_key: str) -> str:
        return node_id("CanonicalMaterial", canonical_key)

    def family_id(self, family: str) -> str:
        return node_id("IngredientFamily", family)

    def role_id(self, role: str) -> str:
        return node_id("FunctionalRole", role)

    def family_of(self, canonical_key: str) -> str | None:
        """Family node id attached to ``canonical_key``, or ``None``."""
        cid = self.canonical_id(canonical_key)
        fid = self.family_by_canonical.get(cid)
        if fid is None:
            return None
        return fid.split(":", 1)[1]

    def role_of(self, canonical_key: str) -> str | None:
        """Role node id attached to ``canonical_key``, or ``None``."""
        cid = self.canonical_id(canonical_key)
        rid = self.role_by_canonical.get(cid)
        if rid is None:
            return None
        return rid.split(":", 1)[1]

    def suppliers_for_material(self, canonical_key: str) -> set[int]:
        """Union of supplier ids across all raw-product instances of ``canonical_key``."""
        cid = self.canonical_id(canonical_key)
        out: set[int] = set()
        for raw_id in self.raws_by_canonical.get(cid, set()):
            for sid in self.suppliers_by_raw.get(raw_id, set()):
                out.add(int(sid.split(":", 1)[1]))
        return out

    def companies_for_material(self, canonical_key: str) -> set[int]:
        """Union of company ids that own a raw-product instance of ``canonical_key``."""
        cid = self.canonical_id(canonical_key)
        out: set[int] = set()
        for raw_id in self.raws_by_canonical.get(cid, set()):
            owner = self.owner_by_raw.get(raw_id)
            if owner is not None:
                out.add(int(owner.split(":", 1)[1]))
        return out

    def materials_in_family(self, family: str) -> list[str]:
        """Canonical keys belonging to ``family`` (sorted)."""
        fid = self.family_id(family)
        return sorted(
            cid.split(":", 1)[1] for cid in self.canonicals_by_family.get(fid, set())
        )

    def materials_in_role(self, role: str) -> list[str]:
        """Canonical keys with ``role`` (sorted)."""
        rid = self.role_id(role)
        return sorted(
            cid.split(":", 1)[1] for cid in self.canonicals_by_role.get(rid, set())
        )

    def companies_using_family(self, family: str) -> set[int]:
        """Distinct company ids using any canonical material in ``family``."""
        out: set[int] = set()
        for ck in self.materials_in_family(family):
            out.update(self.companies_for_material(ck))
        return out

    def neighbors_of_material(self, canonical_key: str) -> dict[str, list[str]]:
        """
        Structured neighborhood for a canonical material.

        Returns a dict with keys: ``family``, ``role``, ``raw_products``,
        ``suppliers``, ``companies``; all inner lists are sorted for determinism.
        """
        fam = self.family_of(canonical_key)
        role = self.role_of(canonical_key)
        suppliers = sorted(self.suppliers_for_material(canonical_key))
        companies = sorted(self.companies_for_material(canonical_key))
        cid = self.canonical_id(canonical_key)
        raws = sorted(
            int(rid.split(":", 1)[1]) for rid in self.raws_by_canonical.get(cid, set())
        )
        return {
            "family": [fam] if fam else [],
            "role": [role] if role else [],
            "raw_products": [str(r) for r in raws],
            "suppliers": [str(s) for s in suppliers],
            "companies": [str(c) for c in companies],
        }

    def canonical_keys(self) -> list[str]:
        """Sorted list of canonical keys in the graph."""
        out: list[str] = []
        for n in self.nodes_by_kind.get("CanonicalMaterial", []):
            out.append(n.id.split(":", 1)[1])
        return sorted(out)
