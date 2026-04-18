"""Smoke tests for the supply-network endpoint + its bundle integration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agnes.api.main import create_app

DB_PATH = Path("data/raw/db.sqlite")
ENTITY_COUNTS = Path("outputs/reports/entity_counts.json")


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.mark.skipif(not DB_PATH.is_file(), reason="Challenge SQLite DB not present")
def test_supply_network_aggregates_match_entity_counts(client: TestClient) -> None:
    resp = client.get("/api/supply-network")
    assert resp.status_code == 200
    body = resp.json()

    assert body["schema_version"] == "1.0.0"
    agg = body["aggregates"]
    if ENTITY_COUNTS.is_file():
        ec = json.loads(ENTITY_COUNTS.read_text())
        assert agg["n_companies"] == ec["Company"]
        assert agg["n_suppliers"] == ec["Supplier"]
        assert agg["n_finished_goods"] == ec["FinishedGood"]
        assert agg["n_raw_materials"] == ec["RawMaterial"]
        assert agg["n_supplier_products"] == ec["Supplier_Product"]
        assert agg["n_bom_edges"] == ec["BOM_Component"]

    # node-list shape
    assert len(body["companies"]) == agg["n_companies"]
    assert len(body["suppliers"]) == agg["n_suppliers"]
    assert len(body["products"]) == agg["n_finished_goods"] + agg["n_raw_materials"]
    assert len(body["supplier_product_edges"]) == agg["n_supplier_products"]
    assert len(body["product_raw_edges"]) == agg["n_bom_edges"]


@pytest.mark.skipif(not DB_PATH.is_file(), reason="Challenge SQLite DB not present")
def test_supply_network_referential_integrity(client: TestClient) -> None:
    body = client.get("/api/supply-network").json()
    supplier_ids = {s["id"] for s in body["suppliers"]}
    company_ids = {c["id"] for c in body["companies"]}
    product_ids = {p["id"] for p in body["products"]}

    for edge in body["supplier_product_edges"]:
        assert edge["supplier_id"] in supplier_ids
        assert edge["company_id"] in company_ids
        assert edge["product_id"] in product_ids

    for edge in body["company_supplier_edges"]:
        assert edge["supplier_id"] in supplier_ids
        assert edge["company_id"] in company_ids

    for edge in body["product_raw_edges"]:
        assert edge["company_id"] in company_ids
        assert edge["finished_product_id"] in product_ids
        assert edge["raw_product_id"] in product_ids

    # supplier_raw_edges must be a subset of supplier_product_edges (by id pair)
    sp_pairs = {(e["supplier_id"], e["product_id"]) for e in body["supplier_product_edges"]}
    for edge in body["supplier_raw_edges"]:
        assert (edge["supplier_id"], edge["raw_product_id"]) in sp_pairs
        assert edge["canonical_key"] is not None


@pytest.mark.skipif(not DB_PATH.is_file(), reason="Challenge SQLite DB not present")
def test_supply_network_supplier_product_sum(client: TestClient) -> None:
    body = client.get("/api/supply-network").json()
    total = sum(s["product_count"] for s in body["suppliers"])
    assert total == body["aggregates"]["n_supplier_products"]


@pytest.mark.skipif(not DB_PATH.is_file(), reason="Challenge SQLite DB not present")
def test_supply_network_included_in_dashboard(client: TestClient) -> None:
    body = client.get("/api/dashboard").json()
    assert "supply_network" in body
    assert body["supply_network"] is not None
    assert "supply_network" not in body["missing"]
    sn = body["supply_network"]
    assert sn["aggregates"]["n_companies"] > 0
    assert sn["aggregates"]["n_suppliers"] > 0
