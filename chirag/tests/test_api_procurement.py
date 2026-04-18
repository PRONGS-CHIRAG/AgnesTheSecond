"""Integration tests for the /api/procurement/* router."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _seed_db(db_path: Path, *, with_procurement: bool = True) -> None:
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE Company (Id INTEGER PRIMARY KEY, Name TEXT);
        CREATE TABLE Supplier (Id INTEGER PRIMARY KEY, Name TEXT);
        CREATE TABLE Product (
            Id INTEGER PRIMARY KEY, SKU TEXT, Type TEXT, CompanyId INTEGER
        );
        CREATE TABLE BOM (Id INTEGER PRIMARY KEY, ProducedProductId INTEGER);
        CREATE TABLE BOM_Component (BOMId INTEGER, ConsumedProductId INTEGER);
        CREATE TABLE Supplier_Product (SupplierId INTEGER, ProductId INTEGER);

        INSERT INTO Company VALUES (1, 'Acme');
        INSERT INTO Supplier VALUES (10, 'Alpha Co');
        INSERT INTO Supplier VALUES (11, 'Bravo Inc');
        INSERT INTO Supplier VALUES (12, 'Charlie Ltd');
        INSERT INTO Product VALUES
            (100, 'RM-C1-whey-protein-deadbeef', 'raw-material', 1);
        INSERT INTO Product VALUES
            (101, 'RM-C1-sunflower-oil-cafebabe', 'raw-material', 1);
        """
    )
    if with_procurement:
        conn.executescript(
            """
            CREATE TABLE Supplier_Rating (
                SupplierId INTEGER PRIMARY KEY,
                QualityScore REAL, ComplianceScore REAL, ReliabilityScore REAL,
                LeadTimeDays INTEGER, MinOrderQty INTEGER, Certifications TEXT,
                LastAuditDate TEXT, RiskTier TEXT
            );
            CREATE TABLE Price_Benchmark (
                BaseName TEXT PRIMARY KEY,
                AvgMarketPrice REAL, MinPrice REAL, MaxPrice REAL,
                PriceVolatility REAL, LastUpdated TEXT
            );
            CREATE TABLE Procurement_History (
                Id INTEGER PRIMARY KEY AUTOINCREMENT,
                SupplierId INTEGER, ProductId INTEGER, CompanyId INTEGER,
                OrderDate TEXT, DeliveryDate TEXT,
                Quantity REAL, UnitPrice REAL, TotalCost REAL,
                Currency TEXT DEFAULT 'USD',
                OnTime INTEGER, QualityPassRate REAL
            );

            -- Alpha: cheap + qualified (quality 90, compliance 88).
            INSERT INTO Supplier_Rating VALUES
                (10, 90, 88, 92, 14, 500, 'GMP,ISO-22000', '2025-06-01', 'low');
            -- Bravo: expensive but qualified.
            INSERT INTO Supplier_Rating VALUES
                (11, 82, 85, 80, 21, 250, 'ISO-22000', '2025-05-01', 'medium');
            -- Charlie: cheap but disqualified.
            INSERT INTO Supplier_Rating VALUES
                (12, 60, 55, 65, 30, 100, '', '2024-12-01', 'high');

            INSERT INTO Price_Benchmark VALUES
                ('whey-protein', 20.0, 16.0, 25.0, 0.12, '2026-04-01');

            -- whey-protein: Alpha $15 (cheap, qualified) vs Bravo $25 (spread 40%).
            INSERT INTO Procurement_History
                (SupplierId, ProductId, CompanyId, OrderDate, DeliveryDate,
                 Quantity, UnitPrice, TotalCost, Currency, OnTime, QualityPassRate)
                VALUES
                (10, 100, 1, '2025-02-01', '2025-02-15',
                 1000, 15.0, 15000, 'USD', 1, 98.0),
                (11, 100, 1, '2025-02-10', '2025-02-25',
                 800, 25.0, 20000, 'USD', 0, 90.0);

            -- sunflower-oil: only Alpha supplies it (single supplier, no savings).
            INSERT INTO Procurement_History
                (SupplierId, ProductId, CompanyId, OrderDate, DeliveryDate,
                 Quantity, UnitPrice, TotalCost, Currency, OnTime, QualityPassRate)
                VALUES
                (10, 101, 1, '2025-03-01', '2025-03-12',
                 500, 8.0, 4000, 'USD', 1, 97.0);
            """
        )
    conn.commit()
    conn.close()


@pytest.fixture
def seeded_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "supply.sqlite"
    _seed_db(db_path, with_procurement=True)
    monkeypatch.setenv("AGNES_DB_PATH", str(db_path))
    monkeypatch.setenv("AGNES_REPORTS_DIR", str(tmp_path / "reports"))
    (tmp_path / "reports").mkdir(parents=True, exist_ok=True)
    from agnes.api.main import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def partial_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "supply.sqlite"
    _seed_db(db_path, with_procurement=False)
    monkeypatch.setenv("AGNES_DB_PATH", str(db_path))
    monkeypatch.setenv("AGNES_REPORTS_DIR", str(tmp_path / "reports"))
    (tmp_path / "reports").mkdir(parents=True, exist_ok=True)
    from agnes.api.main import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c


class TestOverview:
    def test_aggregates_spend_and_suppliers(self, seeded_app: TestClient) -> None:
        resp = seeded_app.get("/api/procurement/overview")
        assert resp.status_code == 200
        body = resp.json()
        assert body["partial"] is False
        assert body["total_spend"] == 39000.0
        assert body["n_orders"] == 3
        assert body["n_suppliers"] == 2
        assert body["n_ingredients"] == 2
        # 2 out of 3 orders on time => 66.67%
        assert 60 < body["on_time_rate"] < 70

        top = {s["supplier_name"]: s for s in body["top_suppliers"]}
        assert "Alpha Co" in top and "Bravo Inc" in top
        assert top["Bravo Inc"]["total_spend"] == 20000.0

        ings = {i["base_name"]: i for i in body["top_ingredients"]}
        assert ings["whey-protein"]["n_suppliers"] == 2
        assert ings["sunflower-oil"]["n_suppliers"] == 1

    def test_overview_partial_when_missing_tables(
        self, partial_app: TestClient
    ) -> None:
        resp = partial_app.get("/api/procurement/overview")
        assert resp.status_code == 200
        body = resp.json()
        assert body["partial"] is True
        assert body["n_orders"] == 0
        assert body["top_suppliers"] == []


class TestSavings:
    def test_surfaces_qualifying_spread(self, seeded_app: TestClient) -> None:
        resp = seeded_app.get("/api/procurement/savings")
        assert resp.status_code == 200
        body = resp.json()
        assert body["partial"] is False
        names = [o["base_name"] for o in body["opportunities"]]
        assert "whey-protein" in names

        whey = next(o for o in body["opportunities"] if o["base_name"] == "whey-protein")
        assert whey["meets_gates"] is True
        assert whey["best_supplier_name"] == "Alpha Co"
        assert whey["spread_pct"] >= 15.0
        assert whey["estimated_savings_usd"] > 0.0
        assert body["total_estimated_savings_usd"] >= whey["estimated_savings_usd"]

    def test_skips_single_supplier(self, seeded_app: TestClient) -> None:
        resp = seeded_app.get("/api/procurement/savings")
        body = resp.json()
        names = [o["base_name"] for o in body["opportunities"]]
        # sunflower-oil has a single supplier — no opportunity emitted.
        assert "sunflower-oil" not in names

    def test_partial_when_missing(self, partial_app: TestClient) -> None:
        resp = partial_app.get("/api/procurement/savings")
        assert resp.status_code == 200
        body = resp.json()
        assert body["partial"] is True
        assert body["opportunities"] == []


class TestSuppliers:
    def test_per_supplier_rollup(self, seeded_app: TestClient) -> None:
        resp = seeded_app.get("/api/procurement/suppliers")
        assert resp.status_code == 200
        body = resp.json()
        assert body["partial"] is False
        alpha = next(
            s for s in body["suppliers"] if s["supplier_name"] == "Alpha Co"
        )
        assert alpha["n_orders"] == 2
        assert alpha["n_ingredients"] == 2
        assert alpha["on_time_rate"] == 100.0
        assert alpha["quality_score"] == 90.0
        assert alpha["risk_tier"] == "low"
        assert "GMP" in alpha["certifications"]

    def test_suppliers_partial_when_missing(
        self, partial_app: TestClient
    ) -> None:
        resp = partial_app.get("/api/procurement/suppliers")
        assert resp.status_code == 200
        body = resp.json()
        assert body["partial"] is True
        assert body["suppliers"] == []
