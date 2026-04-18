"""SQLite access helpers."""

from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from agnes.config.settings import Settings

CORE_TABLES = (
    "Company",
    "Product",
    "BOM",
    "BOM_Component",
    "Supplier",
    "Supplier_Product",
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
