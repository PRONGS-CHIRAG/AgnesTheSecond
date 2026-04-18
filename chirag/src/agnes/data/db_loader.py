"""SQLite access helpers."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from agnes.config.settings import Settings
from agnes.models.procurement import (
    PriceBenchmark,
    ProcurementOrder,
    SupplierRating,
)

CORE_TABLES = (
    "Company",
    "Product",
    "BOM",
    "BOM_Component",
    "Supplier",
    "Supplier_Product",
)

PROCUREMENT_TABLES = (
    "Supplier_Rating",
    "Price_Benchmark",
    "Procurement_History",
)


def get_engine(settings: Settings) -> Engine:
    """Create a SQLAlchemy engine for the challenge SQLite file."""
    db_path: Path = settings.db_path.resolve()
    if not db_path.is_file():
        msg = f"Database file not found: {db_path}"
        raise FileNotFoundError(msg)
    return create_engine(f"sqlite:///{db_path}", future=True)


def ping(settings: Settings) -> dict[str, int]:
    """Return row counts for the six core tables; raises on connection failure."""
    engine = get_engine(settings)
    counts: dict[str, int] = {}
    with engine.connect() as conn:
        for table in CORE_TABLES:
            result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
            row = result.fetchone()
            counts[table] = int(row[0]) if row is not None else 0
    return counts


def _existing_tables(engine: Engine) -> set[str]:
    return set(inspect(engine).get_table_names())


def procurement_tables_present(engine: Engine) -> bool:
    """True iff all three procurement tables exist (irrespective of row count)."""
    tables = _existing_tables(engine)
    return all(t in tables for t in PROCUREMENT_TABLES)


def _require_procurement(engine: Engine, settings: Settings) -> bool:
    """Return True if loaders should return non-empty data.

    Honors ``settings.procurement_required``: when True and tables are missing
    we raise; when False we degrade gracefully by returning empty collections.
    """
    present = procurement_tables_present(engine)
    if not present and settings.procurement_required:
        msg = (
            "Procurement tables are required (AGNES_PROCUREMENT_REQUIRED=true) "
            "but one or more of Supplier_Rating, Price_Benchmark, "
            "Procurement_History is missing. Run scripts/seed_procurement_mock.py "
            "--apply to populate them."
        )
        raise RuntimeError(msg)
    return present


def _parse_date(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def _split_certs(raw: object) -> tuple[str, ...]:
    if raw is None:
        return ()
    text_val = str(raw).strip()
    if not text_val:
        return ()
    return tuple(part.strip() for part in text_val.split(",") if part.strip())


def load_supplier_ratings(
    engine: Engine,
    settings: Settings | None = None,
) -> dict[int, SupplierRating]:
    """Return ``{SupplierId: SupplierRating}``; empty if table is missing."""
    settings = settings or Settings()
    if not _require_procurement(engine, settings):
        return {}
    out: dict[int, SupplierRating] = {}
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT SupplierId, QualityScore, ComplianceScore, ReliabilityScore, "
                "LeadTimeDays, MinOrderQty, Certifications, LastAuditDate, RiskTier "
                "FROM Supplier_Rating"
            )
        ).mappings()
        for row in rows:
            rating = SupplierRating(
                SupplierId=int(row["SupplierId"]),
                QualityScore=float(row["QualityScore"] or 0.0),
                ComplianceScore=float(row["ComplianceScore"] or 0.0),
                ReliabilityScore=float(row["ReliabilityScore"] or 0.0),
                LeadTimeDays=int(row["LeadTimeDays"] or 0),
                MinOrderQty=int(row["MinOrderQty"] or 0),
                Certifications=_split_certs(row["Certifications"]),
                LastAuditDate=_parse_date(row["LastAuditDate"]),
                RiskTier=(row["RiskTier"] or "medium").lower(),  # type: ignore[arg-type]
            )
            out[rating.SupplierId] = rating
    return out


def load_price_benchmarks(
    engine: Engine,
    settings: Settings | None = None,
) -> dict[str, PriceBenchmark]:
    """Return ``{base_name: PriceBenchmark}``; empty if table is missing."""
    settings = settings or Settings()
    if not _require_procurement(engine, settings):
        return {}
    out: dict[str, PriceBenchmark] = {}
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT BaseName, AvgMarketPrice, MinPrice, MaxPrice, "
                "PriceVolatility, LastUpdated FROM Price_Benchmark"
            )
        ).mappings()
        for row in rows:
            bn = str(row["BaseName"]).strip().lower()
            if not bn:
                continue
            out[bn] = PriceBenchmark(
                BaseName=bn,
                AvgMarketPrice=float(row["AvgMarketPrice"] or 0.0),
                MinPrice=float(row["MinPrice"] or 0.0),
                MaxPrice=float(row["MaxPrice"] or 0.0),
                PriceVolatility=float(row["PriceVolatility"] or 0.0),
                LastUpdated=_parse_date(row["LastUpdated"]),
            )
    return out


def load_procurement_history(
    engine: Engine,
    settings: Settings | None = None,
    *,
    since: date | None = None,
) -> Iterator[ProcurementOrder]:
    """Stream ``ProcurementOrder`` rows; empty iterator when table is missing."""
    settings = settings or Settings()
    if not _require_procurement(engine, settings):
        return iter(())
    params: dict[str, object] = {}
    sql = (
        "SELECT Id, SupplierId, ProductId, CompanyId, OrderDate, DeliveryDate, "
        "Quantity, UnitPrice, TotalCost, Currency, OnTime, QualityPassRate "
        "FROM Procurement_History"
    )
    if since is not None:
        sql += " WHERE OrderDate >= :since"
        params["since"] = since.strftime("%Y-%m-%d")

    def _iter() -> Iterator[ProcurementOrder]:
        with engine.connect() as conn:
            result = conn.execute(text(sql), params).mappings()
            for row in result:
                order_date = _parse_date(row["OrderDate"])
                if order_date is None:
                    continue
                yield ProcurementOrder(
                    Id=int(row["Id"]),
                    SupplierId=int(row["SupplierId"]),
                    ProductId=int(row["ProductId"]),
                    CompanyId=int(row["CompanyId"]),
                    OrderDate=order_date,
                    DeliveryDate=_parse_date(row["DeliveryDate"]),
                    Quantity=float(row["Quantity"] or 0.0),
                    UnitPrice=float(row["UnitPrice"] or 0.0),
                    TotalCost=float(row["TotalCost"] or 0.0),
                    Currency=str(row["Currency"] or "USD"),
                    OnTime=bool(row["OnTime"]),
                    QualityPassRate=float(row["QualityPassRate"] or 0.0),
                )

    return _iter()
