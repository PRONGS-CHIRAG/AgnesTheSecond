"""Fixed ingredient-family and functional-role taxonomy (Phase 2)."""

from __future__ import annotations

from typing import Final

TAXONOMY_VERSION: Final[str] = "v2"

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

# --- Keyword catalogs -------------------------------------------------------
# Each chirag ``FAMILIES`` entry gets a (possibly empty) tuple of keyword
# substrings. ``classify_family`` scores a free-text ingredient name by summing
# lengths of matched keywords and returns the highest-scoring family; ties go
# to ``"other"``. Ported from ``taim/insights/agnes_engine.py::FUNCTIONAL_CATEGORIES``;
# taim's 18 categories are mapped onto chirag's 16 families as follows:
#
#   taim                    -> chirag
#   -----                      -------
#   protein                 -> amino_acid_protein
#   sweetener               -> sweetener
#   emulsifier              -> emulsifier
#   vitamin + mineral +
#     salt_electrolyte      -> vitamin_mineral
#   fiber                   -> carbohydrate_starch
#   fat_oil                 -> lipid_fat
#   flavor                  -> flavorant
#   thickener_stabilizer    -> thickener_stabilizer
#   preservative            -> preservative
#   acid                    -> acidulant
#   color                   -> colorant
#   botanical + probiotic   -> herbal_botanical
#   capsule_coating         -> packaging_aid
#   excipient               -> excipient_binder

FAMILY_KEYWORDS: Final[dict[str, tuple[str, ...]]] = {
    "acidulant": (
        "citric-acid", "malic-acid", "lactic-acid", "tartaric-acid",
        "stearic-acid", "dl-tartaric",
    ),
    "amino_acid_protein": (
        "protein", "collagen", "peptide", "casein", "whey", "bcaa",
        "l-leucine", "l-isoleucine", "l-valine", "leucine", "amino-acid",
    ),
    "carbohydrate_starch": (
        "fiber", "fibre", "inulin", "psyllium", "prebiotic",
        "fructooligosaccharide", "tapioca-fiber",
    ),
    "colorant": (
        "color", "lake", "caramel", "annatto", "turmeric", "beet-extract",
        "beet-juice", "titanium-dioxide", "blue-2", "red-40", "yellow-6",
        "fd-and-c",
    ),
    "emulsifier": (
        "lecithin", "polysorbate", "glyceride", "acetoglyceride",
    ),
    "excipient_binder": (
        "microcrystalline-cellulose", "cellulose", "silica", "silicon-dioxide",
        "magnesium-stearate", "talc", "dicalcium-phosphate",
        "tricalcium-phosphate", "rice-flour", "rice-powder", "rice-bran",
        "modified-cellulose", "modified-food-starch", "sodium-alginate",
        "potassium-alginate",
    ),
    "flavorant": (
        "flavor", "flavour", "vanilla", "chocolate", "cocoa", "cinnamon",
        "cherry", "strawberry", "peach", "tangerine", "lemon", "passionfruit",
        "orange-flavor", "ginger",
    ),
    "herbal_botanical": (
        "extract", "herb", "botanical", "rhodiola", "ashwagandha", "green-tea",
        "grape-seed", "pomegranate", "alfalfa", "black-pepper", "astaxanthin",
        "lutein", "lycopene", "zeaxanthin", "resveratrol", "bioflavonoid",
        "hesperidin", "rutin", "coenzyme", "coq10", "epicor", "taurine",
        "probiotic", "bifidobacterium", "lactobacillus", "ferment", "cultured",
    ),
    "lipid_fat": (
        "oil", "mct", "coconut-mct", "medium-chain-triglyceride", "safflower",
        "soybean-oil", "corn-oil", "palm-oil", "olive-oil", "sunflower-oil",
    ),
    "other": (),
    "packaging_aid": (
        "capsule", "coating", "softgel", "hypromellose", "hpmc",
        "hydroxypropyl", "pharmaceutical-glaze", "lac-resin", "carnauba-wax",
        "zein", "polyvinyl", "polyethylene", "croscarmellose",
        "sodium-starch-glycolate", "plantgel", "vegan-capsule",
        "gelatin-capsule", "vegetarian-capsule",
    ),
    "preservative": (
        "benzoate", "sorbate", "sorbic-acid", "bht", "rosemary-extract",
    ),
    "solvent_carrier": (),
    "sweetener": (
        "sugar", "stevia", "monk-fruit", "erythritol", "sucralose", "sucrose",
        "fructose", "dextrose", "maltodextrin", "sorbitol", "agave",
        "coconut-sugar", "cane-sugar", "rebaudioside", "acesulfame",
        "tapioca-syrup", "polydextrose",
    ),
    "thickener_stabilizer": (
        "gum", "starch", "pectin", "agar", "carrageenan", "gelatin", "gellan",
        "xanthan", "cellulose-gum", "cellulose-gel", "acacia", "gum-arabic",
        "gum-acacia", "gummy-base",
    ),
    "vitamin_mineral": (
        "vitamin", "ascorbic", "retinol", "tocopherol", "thiamin", "thiamine",
        "riboflavin", "niacin", "niacinamide", "nicotinamide", "folate",
        "folic", "biotin", "cobalamin", "cyanocobalamin", "methylcobalamin",
        "pantothen", "pyridoxine", "cholecalciferol", "phytonadione",
        "menaquinone", "retinyl", "ascorbyl", "beta-carotene", "b-vitamins",
        "d-alpha-tocopheryl", "dl-alpha-tocopheryl", "tocopherols",
        "calcium", "magnesium", "zinc", "iron", "selenium", "chromium",
        "copper", "manganese", "potassium", "phosphorus", "iodine", "iodide",
        "boron", "molybdenum", "vanadium", "sodium-selenite",
        "sodium-molybdate", "ferrous", "cupric", "trace-mineral", "concentrace",
        "salt", "sodium-chloride", "himalayan", "sea-salt", "kalahari",
        "chloride", "dipotassium-phosphate", "potassium-chloride",
        "sodium-citrate",
    ),
}

ALLERGEN_MARKERS: Final[dict[str, tuple[str, ...]]] = {
    "soy": ("soy", "soja", "soybean"),
    "dairy": ("whey", "casein", "milk", "lactose", "dairy"),
    "gluten": ("wheat", "gluten", "barley", "rye"),
    "tree_nut": ("almond", "cashew", "walnut", "pecan", "hazelnut", "coconut"),
    "egg": ("egg", "albumin"),
    "bovine": ("bovine", "bone-gelatin"),
    "fish": ("fish", "cod", "salmon"),
}

QUALITY_FLAGS: Final[dict[str, tuple[str, ...]]] = {
    "organic": ("organic",),
    "non_gmo": ("non-gmo",),
    "vegan": ("vegan", "vegetable", "plant"),
    "natural": ("natural",),
    "artificial": ("artificial",),
    "grass_fed": ("grass-fed",),
}


def classify_family(name: str, default: str = "other") -> str:
    """Length-weighted keyword match against ``FAMILY_KEYWORDS``.

    Returns the highest-scoring family, ``default`` when no keyword hits.
    """
    if not name:
        return default
    haystack = name.lower()
    scores: dict[str, int] = {}
    for family, keywords in FAMILY_KEYWORDS.items():
        for kw in keywords:
            if kw and kw in haystack:
                scores[family] = scores.get(family, 0) + len(kw)
    if not scores:
        return default
    return max(scores, key=lambda k: scores[k])


def detect_allergens(name: str) -> tuple[str, ...]:
    """Return a sorted tuple of allergen keys that appear in ``name``."""
    if not name:
        return ()
    haystack = name.lower()
    hits = {key for key, markers in ALLERGEN_MARKERS.items()
            if any(m in haystack for m in markers)}
    return tuple(sorted(hits))


def detect_quality_flags(name: str) -> tuple[str, ...]:
    """Return a sorted tuple of quality flags that appear in ``name``."""
    if not name:
        return ()
    haystack = name.lower()
    hits = {key for key, markers in QUALITY_FLAGS.items()
            if any(m in haystack for m in markers)}
    return tuple(sorted(hits))
