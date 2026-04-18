"""Tool executors for the conversational chat agent.

Each executor is a pure function that takes parsed JSON args and returns a
JSON-serialisable dict. Kept in a dedicated module so they're unit-testable
without spinning up FastAPI or OpenAI.

Security:
    :func:`execute_sql` enforces a strict SQL guard rail — only a single
    ``SELECT`` statement is allowed, with no trailing semicolons, no CTE write
    operations, no pragmas and no ``ATTACH`` calls. The result set is capped at
    50 rows to protect the demo budget.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from agnes.api.services.artifact_loader import ArtifactLoader, ArtifactMissingError

_MAX_ROWS = 50

_FORBIDDEN_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|TRUNCATE|"
    r"GRANT|REVOKE|ATTACH|DETACH|PRAGMA|VACUUM)\b",
    re.IGNORECASE,
)


class SQLGuardError(ValueError):
    """Raised when a SQL statement is rejected by :func:`_guard_sql`."""


def _guard_sql(query: str) -> str:
    """Validate that ``query`` is a single read-only SELECT statement.

    Returns the trimmed query. Raises :class:`SQLGuardError` on any violation.
    """

    if not query or not query.strip():
        raise SQLGuardError("empty_query")
    q = query.strip().rstrip(";").strip()
    if ";" in q:
        raise SQLGuardError("multiple_statements_not_allowed")
    if not re.match(r"^\s*(WITH|SELECT)\b", q, re.IGNORECASE):
        raise SQLGuardError("only_select_queries_allowed")
    if _FORBIDDEN_KEYWORDS.search(q):
        raise SQLGuardError("forbidden_keyword_detected")
    if "--" in q or "/*" in q:
        raise SQLGuardError("comments_not_allowed")
    return q


def tool_execute_sql(engine: Engine, query: str) -> dict[str, Any]:
    """Execute a guarded SELECT and return up to 50 rows as JSON-friendly dicts."""

    try:
        safe_sql = _guard_sql(query)
    except SQLGuardError as exc:
        return {"error": str(exc)}
    try:
        with engine.connect() as conn:
            result = conn.execute(text(safe_sql))
            columns = list(result.keys())
            rows_raw = result.fetchmany(_MAX_ROWS + 1)
    except Exception as exc:  # noqa: BLE001 - surface db errors to the agent
        return {"error": f"sql_execution_failed: {exc}"}

    truncated = len(rows_raw) > _MAX_ROWS
    rows_raw = rows_raw[:_MAX_ROWS]
    rows: list[dict[str, Any]] = []
    for r in rows_raw:
        rec: dict[str, Any] = {}
        for col, val in zip(columns, r, strict=False):
            rec[col] = val if _is_json_scalar(val) else str(val)
        rows.append(rec)
    return {
        "columns": columns,
        "rows": rows,
        "total": len(rows),
        "truncated": truncated,
    }


def _is_json_scalar(val: Any) -> bool:
    return val is None or isinstance(val, (int, float, str, bool))


def tool_find_candidates(
    loader: ArtifactLoader,
    source_key: str,
    limit: int = 10,
) -> dict[str, Any]:
    """Return Phase 4 substitute candidates for a canonical source key."""

    try:
        report = loader.get_candidates()
    except ArtifactMissingError:
        return {"error": "phase4_candidates_missing"}

    hits = [
        c.model_dump(mode="json")
        for c in report.candidates
        if c.source_key == source_key
    ][:limit]
    return {
        "source_key": source_key,
        "total": len(hits),
        "candidates": hits,
        "schema_version": report.schema_version,
    }


def tool_get_evidence(
    loader: ArtifactLoader,
    source_key: str,
    candidate_key: str,
) -> dict[str, Any]:
    """Return Phase 5 evidence for one (source, candidate) pair."""

    try:
        report = loader.get_evidence()
    except ArtifactMissingError:
        return {"error": "phase5_evidence_missing"}

    for item in report.items:
        if item.source_key == source_key and item.candidate_key == candidate_key:
            return {"evidence": item.model_dump(mode="json")}
    return {
        "error": "evidence_pair_not_found",
        "source_key": source_key,
        "candidate_key": candidate_key,
    }


def tool_get_recommendation(
    loader: ArtifactLoader,
    source_key: str,
) -> dict[str, Any]:
    """Return the Phase 7 opportunity + top rows for a given source key."""

    try:
        report = loader.get_recommendations()
    except ArtifactMissingError:
        return {"error": "phase7_recommendations_missing"}

    opp = next(
        (o for o in report.opportunities if o.source_key == source_key), None
    )
    if opp is None:
        return {"error": "source_not_found", "source_key": source_key}
    rows = [r for r in report.items if r.source_key == source_key]
    top_keys = set(opp.top_row_keys)
    top_rows = [r for r in rows if r.row_key() in top_keys]
    return {
        "opportunity": opp.model_dump(mode="json"),
        "top_rows": [r.model_dump(mode="json") for r in top_rows],
        "n_rows": len(rows),
    }


def tool_get_risks(
    loader: ArtifactLoader,
    severity: str | None = None,
    type_: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Return Phase 6.5 supply-risk items, optionally filtered by severity/type."""

    try:
        report = loader.get_risks()
    except ArtifactMissingError:
        return {"error": "phase6_5_risks_missing"}

    items = report.items
    if severity:
        items = [i for i in items if i.severity == severity]
    if type_:
        items = [i for i in items if i.type == type_]
    items = items[:limit]
    return {
        "n_total": report.n_total,
        "by_severity": dict(report.by_severity),
        "by_type": dict(report.by_type),
        "items": [i.model_dump(mode="json") for i in items],
        "schema_version": report.schema_version,
    }


def tool_analyze_bom(
    engine: Engine,
    search_term: str,
) -> dict[str, Any]:
    """Summarise a finished-good BOM: components, suppliers, single-source flags."""

    pattern = f"%{search_term}%"
    try:
        with engine.connect() as conn:
            product_row = conn.execute(
                text(
                    "SELECT p.Id, p.SKU, p.CompanyId, c.Name AS CompanyName "
                    "FROM Product p "
                    "JOIN Company c ON c.Id = p.CompanyId "
                    "WHERE p.Type = 'finished-good' "
                    "  AND (p.SKU LIKE :q OR c.Name LIKE :q) "
                    "LIMIT 1"
                ),
                {"q": pattern},
            ).fetchone()
            if product_row is None:
                return {"error": "finished_good_not_found", "search_term": search_term}

            bom_row = conn.execute(
                text("SELECT Id FROM BOM WHERE ProducedProductId = :pid LIMIT 1"),
                {"pid": product_row.Id},
            ).fetchone()
            if bom_row is None:
                return {
                    "error": "bom_not_found",
                    "product_id": int(product_row.Id),
                    "sku": product_row.SKU,
                }

            components = conn.execute(
                text(
                    "SELECT p.Id, p.SKU FROM BOM_Component bc "
                    "JOIN Product p ON p.Id = bc.ConsumedProductId "
                    "WHERE bc.BOMId = :bid "
                    "ORDER BY p.SKU"
                ),
                {"bid": bom_row.Id},
            ).fetchall()

            results: list[dict[str, Any]] = []
            for comp in components:
                suppliers = conn.execute(
                    text(
                        "SELECT s.Id, s.Name FROM Supplier_Product sp "
                        "JOIN Supplier s ON s.Id = sp.SupplierId "
                        "WHERE sp.ProductId = :cid"
                    ),
                    {"cid": comp.Id},
                ).fetchall()
                results.append(
                    {
                        "product_id": int(comp.Id),
                        "sku": comp.SKU,
                        "supplier_count": len(suppliers),
                        "single_source": len(suppliers) == 1,
                        "suppliers": [
                            {"id": int(s.Id), "name": s.Name} for s in suppliers
                        ],
                    }
                )
    except Exception as exc:  # noqa: BLE001 - surface db errors to the agent
        return {"error": f"bom_query_failed: {exc}"}

    return {
        "product": {
            "id": int(product_row.Id),
            "sku": product_row.SKU,
            "company": product_row.CompanyName,
        },
        "component_count": len(results),
        "single_source_count": sum(1 for r in results if r["single_source"]),
        "components": results,
    }


__all__ = [
    "SQLGuardError",
    "tool_analyze_bom",
    "tool_execute_sql",
    "tool_find_candidates",
    "tool_get_evidence",
    "tool_get_recommendation",
    "tool_get_risks",
]
