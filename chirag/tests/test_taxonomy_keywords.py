"""Keyword-based taxonomy classification (Stage B)."""

from __future__ import annotations

import pytest

from agnes.canonicalization.taxonomy import (
    ALLERGEN_MARKERS,
    FAMILIES,
    FAMILY_KEYWORDS,
    QUALITY_FLAGS,
    TAXONOMY_VERSION,
    classify_family,
    detect_allergens,
    detect_quality_flags,
)


def test_version_is_v2() -> None:
    assert TAXONOMY_VERSION == "v2"


def test_every_family_has_a_keyword_entry() -> None:
    missing = set(FAMILIES) - set(FAMILY_KEYWORDS)
    assert not missing, f"missing keyword tuples for families: {missing}"


@pytest.mark.parametrize(
    "name,expected",
    [
        ("vitamin-c-ascorbic-acid", "vitamin_mineral"),
        ("calcium-citrate", "vitamin_mineral"),
        ("whey-protein-isolate", "amino_acid_protein"),
        ("stevia-rebaudioside-a", "sweetener"),
        ("xanthan-gum", "thickener_stabilizer"),
        ("coconut-mct-oil", "lipid_fat"),
        ("annatto-color", "colorant"),
        ("sodium-benzoate", "preservative"),
        ("gelatin-capsule-shell", "packaging_aid"),
        ("microcrystalline-cellulose", "excipient_binder"),
        ("ashwagandha-extract", "herbal_botanical"),
        ("citric-acid", "acidulant"),
        ("inulin-prebiotic-fiber", "carbohydrate_starch"),
        ("lecithin", "emulsifier"),
        ("lactobacillus-acidophilus", "herbal_botanical"),
    ],
)
def test_classify_family(name: str, expected: str) -> None:
    assert classify_family(name) == expected


def test_classify_family_falls_back_to_other() -> None:
    assert classify_family("zzz-unknown-ingredient") == "other"


def test_detect_allergens_multi() -> None:
    allergens = detect_allergens("organic whey protein with soy lecithin")
    assert set(allergens) >= {"dairy", "soy"}


def test_detect_quality_flags_multi() -> None:
    flags = detect_quality_flags("organic non-gmo vegan protein")
    assert set(flags) >= {"organic", "non_gmo", "vegan"}


def test_allergen_markers_shape() -> None:
    for key, markers in ALLERGEN_MARKERS.items():
        assert isinstance(key, str) and markers, key


def test_quality_flags_shape() -> None:
    for key, markers in QUALITY_FLAGS.items():
        assert isinstance(key, str) and markers, key
