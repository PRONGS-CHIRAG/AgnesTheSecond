"""Introspect SQLite schema and row counts."""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from agnes.data import db_loader
from agnes.models.reports import ColumnInfo, ForeignKeyInfo, SchemaSummary, TableSummary


def build_schema_summary(engine: Engine) -> SchemaSummary:
    """Build SchemaSummary for all core tables using SQLAlchemy Inspector."""
    insp = inspect(engine)
    tables_out: list[TableSummary] = []

    for table_name in db_loader.CORE_TABLES:
        if not insp.has_table(table_name):
            continue
        cols = insp.get_columns(table_name)
        pk = insp.get_pk_constraint(table_name).get("constrained_columns") or []
        fks_raw = insp.get_foreign_keys(table_name)
        fks: list[ForeignKeyInfo] = []
        for fk in fks_raw:
            fks.append(
                ForeignKeyInfo(
                    constrained_columns=list(fk.get("constrained_columns") or []),
                    referred_table=str(fk.get("referred_table") or ""),
                    referred_columns=list(fk.get("referred_columns") or []),
                )
            )
        columns = [
            ColumnInfo(
                name=str(c.get("name", "")),
                type=str(c.get("type")) if c.get("type") is not None else None,
                nullable=bool(c.get("nullable", True)),
            )
            for c in cols
        ]
        with engine.connect() as conn:
            rc = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            row = rc.fetchone()
            row_count = int(row[0]) if row is not None else 0

        tables_out.append(
            TableSummary(
                name=table_name,
                row_count=row_count,
                columns=columns,
                primary_key=list(pk),
                foreign_keys=fks,
            )
        )

    return SchemaSummary(tables=tables_out)
