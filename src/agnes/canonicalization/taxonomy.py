"""Fixed ingredient-family and functional-role taxonomy (Phase 2)."""

from __future__ import annotations

from typing import Final

TAXONOMY_VERSION: Final[str] = "v1"

FAMILIES: Final[tuple[str, ...]] = (
    "acidulant",
    "amino_acid_protein",
    "carbohydrate_starch",
    "colorant",
    "emulsifier",
    "excipient_binder",
    "flavorant",
    "herbal_botanical",
    "lipid_fat",
    "other",
    "packaging_aid",
    "preservative",
    "solvent_carrier",
    "sweetener",
    "thickener_stabilizer",
    "vitamin_mineral",
)

ROLES: Final[tuple[str, ...]] = (
    "active_ingredient",
    "binder",
    "bulking",
    "coating",
    "coloring",
    "emulsification",
    "flavoring",
    "flow_agent",
    "other",
    "ph_buffering",
    "preservation",
    "structural",
    "sweetening",
)

FAMILY_SET: Final[frozenset[str]] = frozenset(FAMILIES)
ROLE_SET: Final[frozenset[str]] = frozenset(ROLES)
