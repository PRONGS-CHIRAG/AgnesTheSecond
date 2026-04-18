"""Unit tests for the chat-agent tool dispatchers and SQL safety guard."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from agnes.api.chat_tools import (
    SQLGuardError,
    _guard_sql,
    tool_analyze_bom,
    tool_execute_sql,
)


@pytest.fixture
def supply_db(tmp_path: Path):
    db_path = tmp_path / "supply.sqlite"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE Company (Id INTEGER PRIMARY KEY, Name TEXT);
        CREATE TABLE Product (
            Id INTEGER PRIMARY KEY,
            SKU TEXT,
            CompanyId INTEGER,
            Type TEXT
        );
        CREATE TABLE BOM (Id INTEGER PRIMARY KEY, ProducedProductId INTEGER);
        CREATE TABLE BOM_Component (BOMId INTEGER, ConsumedProductId INTEGER);
        CREATE TABLE Supplier (Id INTEGER PRIMARY KEY, Name TEXT);
        CREATE TABLE Supplier_Product (SupplierId INTEGER, ProductId INTEGER);

        INSERT INTO Company VALUES (1, 'Acme Foods');
        INSERT INTO Product VALUES (10, 'FG-C1-orange-juice-abc', 1, 'finished-good');
        INSERT INTO Product VALUES (11, 'RM-C1-vitamin-c-ascorbic-acid-dead', 1, 'raw-material');
        INSERT INTO Product VALUES (12, 'RM-C1-orange-concentrate-beef', 1, 'raw-material');
        INSERT INTO BOM VALUES (100, 10);
        INSERT INTO BOM_Component VALUES (100, 11);
        INSERT INTO BOM_Component VALUES (100, 12);
        INSERT INTO Supplier VALUES (20, 'Supplier Alpha');
        INSERT INTO Supplier VALUES (21, 'Supplier Beta');
        INSERT INTO Supplier_Product VALUES (20, 11);
        INSERT INTO Supplier_Product VALUES (20, 12);
        INSERT INTO Supplier_Product VALUES (21, 12);
        """
    )
    conn.commit()
    conn.close()
    return create_engine(f"sqlite:///{db_path}")


class TestSQLGuard:
    def test_accepts_simple_select(self) -> None:
        assert _guard_sql("SELECT * FROM Product") == "SELECT * FROM Product"

    def test_strips_trailing_semicolon(self) -> None:
        assert _guard_sql("  SELECT 1;  ") == "SELECT 1"

    def test_accepts_cte(self) -> None:
        q = "WITH x AS (SELECT 1 AS n) SELECT n FROM x"
        assert _guard_sql(q) == q

    @pytest.mark.parametrize(
        "bad",
        [
            "INSERT INTO Product VALUES (99, 'x', 1, 't')",
            "UPDATE Product SET SKU='y' WHERE Id=1",
            "DELETE FROM Product",
            "DROP TABLE Product",
            "ALTER TABLE Product ADD COLUMN x INT",
            "CREATE TABLE x (Id INT)",
            "PRAGMA table_info(Product)",
            "ATTACH DATABASE 'x' AS y",
        ],
    )
    def test_rejects_writes_and_admin(self, bad: str) -> None:
        with pytest.raises(SQLGuardError):
            _guard_sql(bad)

    def test_rejects_multi_statement(self) -> None:
        with pytest.raises(SQLGuardError):
            _guard_sql("SELECT 1; SELECT 2")

    def test_rejects_comments(self) -> None:
        with pytest.raises(SQLGuardError):
            _guard_sql("SELECT 1 -- sneaky")
        with pytest.raises(SQLGuardError):
            _guard_sql("SELECT /* hi */ 1")

    def test_rejects_empty(self) -> None:
        with pytest.raises(SQLGuardError):
            _guard_sql("")


class TestExecuteSQL:
    def test_returns_rows_and_columns(self, supply_db) -> None:
        result = tool_execute_sql(
            supply_db, "SELECT Id, Name FROM Company ORDER BY Id"
        )
        assert "error" not in result
        assert result["columns"] == ["Id", "Name"]
        assert result["rows"] == [{"Id": 1, "Name": "Acme Foods"}]
        assert result["total"] == 1
        assert result["truncated"] is False

    def test_returns_error_for_non_select(self, supply_db) -> None:
        result = tool_execute_sql(
            supply_db, "INSERT INTO Company VALUES (99, 'Hack')"
        )
        assert result == {"error": "only_select_queries_allowed"}

    def test_returns_error_for_forbidden_keyword_in_select(
        self, supply_db
    ) -> None:
        result = tool_execute_sql(
            supply_db, "SELECT * FROM Company WHERE Id = 1 UNION SELECT 1, 'x' FROM (SELECT 1) AS t WHERE 1=1 AND (SELECT 1 WHERE 1=1 OR 1=1 OR 1=1 OR PRAGMA table_info(x))"
        )
        assert result == {"error": "forbidden_keyword_detected"}

    def test_returns_error_for_bad_sql(self, supply_db) -> None:
        result = tool_execute_sql(supply_db, "SELECT * FROM no_such_table")
        assert "error" in result
        assert result["error"].startswith("sql_execution_failed")

    def test_truncates_at_50_rows(self, tmp_path: Path) -> None:
        db_path = tmp_path / "big.sqlite"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE N (v INT)")
        conn.executemany(
            "INSERT INTO N VALUES (?)", [(i,) for i in range(55)]
        )
        conn.commit()
        conn.close()
        engine = create_engine(f"sqlite:///{db_path}")
        result = tool_execute_sql(engine, "SELECT v FROM N")
        assert result["total"] == 50
        assert result["truncated"] is True


class TestAnalyzeBOM:
    def test_summarises_components_and_suppliers(self, supply_db) -> None:
        result = tool_analyze_bom(supply_db, "orange-juice")
        assert "error" not in result
        assert result["product"]["sku"] == "FG-C1-orange-juice-abc"
        assert result["component_count"] == 2
        assert result["single_source_count"] == 1
        skus = {c["sku"]: c for c in result["components"]}
        assert skus["RM-C1-vitamin-c-ascorbic-acid-dead"]["single_source"] is True
        assert (
            skus["RM-C1-orange-concentrate-beef"]["supplier_count"] == 2
        )

    def test_missing_product(self, supply_db) -> None:
        result = tool_analyze_bom(supply_db, "nonexistent-product-xyz")
        assert result == {
            "error": "finished_good_not_found",
            "search_term": "nonexistent-product-xyz",
        }
