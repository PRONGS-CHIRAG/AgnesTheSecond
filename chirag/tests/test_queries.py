"""Tests for relational query helpers."""

from agnes.data import queries


def test_raw_material_usage_non_empty(engine) -> None:
    df = queries.raw_material_usage(engine)
    assert not df.empty
    assert set(df.columns) >= {"RawId", "SKU", "n_boms", "n_finished_goods", "n_companies"}
    assert df["n_companies"].max() >= 1


def test_entity_counts_matches_core_tables(engine) -> None:
    ec = queries.entity_counts(engine).iloc[0].to_dict()
    assert ec["Company"] == 61
    assert ec["Product"] == 1025
    assert ec["BOM"] == 149
    assert ec["FinishedGood"] == ec["BOM"]
    assert ec["RawMaterial"] + ec["FinishedGood"] == ec["Product"]


def test_company_product_tree_shape(engine) -> None:
    tree = queries.company_product_tree(engine)
    assert not tree.empty
    assert "CompanyName" in tree.columns and "RawSKU" in tree.columns
