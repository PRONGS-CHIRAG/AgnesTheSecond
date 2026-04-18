"""Graph schema constants for the Agnes knowledge graph (Phase 3)."""

from __future__ import annotations

from typing import Final, Literal

GRAPH_SCHEMA_VERSION: Final[str] = "v1"
DATASET_NAME: Final[str] = "agnes_kg_v1"

NodeKind = Literal[
    "Company",
    "Supplier",
    "RawProduct",
    "CanonicalMaterial",
    "IngredientFamily",
    "FunctionalRole",
]

EdgeKind = Literal[
    "OWNS",              # Company -> RawProduct
    "INSTANCE_OF",       # RawProduct -> CanonicalMaterial
    "OFFERS",            # Supplier -> RawProduct
    "BELONGS_TO_FAMILY", # CanonicalMaterial -> IngredientFamily
    "HAS_ROLE",          # CanonicalMaterial -> FunctionalRole
    "USED_BY",           # RawProduct -> Company (mirror of OWNS for traversal)
]

NODE_KINDS: Final[tuple[str, ...]] = (
    "Company",
    "Supplier",
    "RawProduct",
    "CanonicalMaterial",
    "IngredientFamily",
    "FunctionalRole",
)

EDGE_KINDS: Final[tuple[str, ...]] = (
    "OWNS",
    "INSTANCE_OF",
    "OFFERS",
    "BELONGS_TO_FAMILY",
    "HAS_ROLE",
    "USED_BY",
)
