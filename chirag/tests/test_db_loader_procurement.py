"""Tests for procurement-aware db_loader helpers."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from agnes.config.settings import Settings
from agnes.data.db_loader import (
    PROCUREMENT_TABLES,
    load_price_benchmarks,
    load_procurement_history,
    load_supplier_ratings,
    procurement_tables_present,
)


@pytest.fixture
def empty_engine(tmp_path: Path):
    db_path = tmp_path / "empty.sqlite"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE Supplier (Id INTEGER PRIMARY KEY, Name TEXT);
        CREATE TABLE Product (Id INTEGER PRIMARY KEY, SKU TEXT, Type TEXT,
                              CompanyId INTEGER);
        CREATE TABLE Company (Id INTEGER PRIMARY KEY, Name TEXT);
        """
    )
    conn.commit()
    conn.close()
    return create_engine(f"sqlite:///{db_path}")


@pytest.fixture
def seeded_engine(tmp_path: Path):
    db_path = tmp_path / "seeded.sqlite"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE Supplier (Id INTEGER PRIMARY KEY, Name TEXT);
        CREATE TABLE Product (Id INTEGER PRIMARY KEY, SKU TEXT, Type TEXT,
                              CompanyId INTEGER);
        CREATE TABLE Company (Id INTEGER PRIMARY KEY, Name TEXT);

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

        INSERT INTO Supplier VALUES (1, 'Acme');
        INSERT INTO Company VALUES (1, 'BetaCo');
        INSERT INTO Product VALUES (10, 'RM-C1-whey-protein-abc123', 'raw-material', 1);
        INSERT INTO Supplier_Rating VALUES
            (1, 90.0, 88.5, 92.0, 14, 500, 'GMP,ISO-22000', '2025-06-01', 'low');
        INSERT INTO Price_Benchmark VALUES
            ('whey-protein', 20.5, 18.0, 23.0, 0.12, '2026-04-01');
        INSERT INTO Procurement_History
            (SupplierId, ProductId, CompanyId, OrderDate, DeliveryDate,
             Quantity, UnitPrice, TotalCost, Currency, OnTime, QualityPassRate)
            VALUES (1, 10, 1, '2025-01-15', '2025-01-29',
                    500, 20.0, 10000, 'USD', 1, 95.5);
        """
    )
    conn.commit()
    conn.close()
    return create_engine(f"sqlite:///{db_path}")


def test_procurement_table_constant_is_stable() -> None:
    assert PROCUREMENT_TABLES == (
        "Supplier_Rating", "Price_Benchmark", "Procurement_History",
    )


def test_loaders_degrade_on_missing_tables(empty_engine) -> None:
    settings = Settings(procurement_required=False)
    assert procurement_tables_present(empty_engine) is False
    assert load_supplier_ratings(empty_engine, settings) == {}
    assert load_price_benchmarks(empty_engine, settings) == {}
    assert list(load_procurement_history(empty_engine, settings)) == []


def test_loaders_raise_when_required(empty_engine) -> None:
    settings = Settings(procurement_required=True)
    with pytest.raises(RuntimeError):
        load_supplier_ratings(empty_engine, settings)


def test_loaders_parse_seeded_rows(seeded_engine) -> None:
    settings = Settings(procurement_required=False)
    ratings = load_supplier_ratings(seeded_engine, settings)
    assert 1 in ratings
    rating = ratings[1]
    assert rating.RiskTier == "low"
    assert rating.Certifications == ("GMP", "ISO-22000")

    bench = load_price_benchmarks(seeded_engine, settings)
    assert "whey-protein" in bench
    assert bench["whey-protein"].AvgMarketPrice == 20.5

    orders = list(load_procurement_history(seeded_engine, settings))
    assert len(orders) == 1
    assert orders[0].OnTime is True
    assert orders[0].TotalCost == 10000.0
