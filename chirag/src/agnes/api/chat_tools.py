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


def _resolve_supplier(
    conn: Any, *, supplier_id: int | None, name: str | None
) -> Any:
    """Find a supplier by id or case-insensitive name fragment."""

    if supplier_id is not None:
        row = conn.execute(
            text("SELECT Id, Name FROM Supplier WHERE Id = :sid"),
            {"sid": int(supplier_id)},
        ).fetchone()
        return row
    if name:
        row = conn.execute(
            text(
                "SELECT Id, Name FROM Supplier "
                "WHERE LOWER(Name) LIKE :q "
                "ORDER BY CASE WHEN LOWER(Name) = :exact THEN 0 ELSE 1 END, Name "
                "LIMIT 1"
            ),
            {"q": f"%{name.lower()}%", "exact": name.lower()},
        ).fetchone()
        return row
    return None


def tool_get_supplier_profile(
    engine: Engine,
    *,
    supplier_id: int | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    """Return a consolidated supplier profile: rating + spend + top products + on-time.

    Accepts either ``supplier_id`` or a name fragment. Aggregates:

    * Supplier_Rating (quality / compliance / reliability / lead time / tier)
    * Procurement_History (total_spend_usd, orders, on-time %, quality pass %)
    * Top 5 products by cumulative spend
    * Distinct customer companies
    """

    if supplier_id is None and not name:
        return {"error": "supplier_id_or_name_required"}

    try:
        with engine.connect() as conn:
            sup = _resolve_supplier(
                conn, supplier_id=supplier_id, name=name
            )
            if sup is None:
                return {
                    "error": "supplier_not_found",
                    "supplier_id": supplier_id,
                    "name": name,
                }

            rating = conn.execute(
                text(
                    "SELECT QualityScore, ComplianceScore, ReliabilityScore, "
                    "LeadTimeDays, MinOrderQty, Certifications, "
                    "LastAuditDate, RiskTier "
                    "FROM Supplier_Rating WHERE SupplierId = :sid"
                ),
                {"sid": int(sup.Id)},
            ).fetchone()

            spend = conn.execute(
                text(
                    "SELECT COUNT(*) AS orders, "
                    "SUM(TotalCost) AS total_spend, "
                    "AVG(OnTime) AS on_time_rate, "
                    "AVG(QualityPassRate) AS quality_pass_rate, "
                    "MIN(OrderDate) AS first_order, "
                    "MAX(OrderDate) AS last_order "
                    "FROM Procurement_History WHERE SupplierId = :sid"
                ),
                {"sid": int(sup.Id)},
            ).fetchone()

            top_products = conn.execute(
                text(
                    "SELECT p.Id, p.SKU, p.Type, "
                    "COUNT(*) AS orders, "
                    "SUM(ph.TotalCost) AS spend "
                    "FROM Procurement_History ph "
                    "JOIN Product p ON p.Id = ph.ProductId "
                    "WHERE ph.SupplierId = :sid "
                    "GROUP BY p.Id "
                    "ORDER BY spend DESC "
                    "LIMIT 5"
                ),
                {"sid": int(sup.Id)},
            ).fetchall()

            companies = conn.execute(
                text(
                    "SELECT DISTINCT c.Id, c.Name "
                    "FROM Procurement_History ph "
                    "JOIN Company c ON c.Id = ph.CompanyId "
                    "WHERE ph.SupplierId = :sid "
                    "ORDER BY c.Name "
                    "LIMIT 10"
                ),
                {"sid": int(sup.Id)},
            ).fetchall()

            distinct_products = conn.execute(
                text(
                    "SELECT COUNT(DISTINCT ProductId) FROM Supplier_Product "
                    "WHERE SupplierId = :sid"
                ),
                {"sid": int(sup.Id)},
            ).scalar()
    except Exception as exc:  # noqa: BLE001
        return {"error": f"supplier_query_failed: {exc}"}

    return {
        "supplier": {"id": int(sup.Id), "name": sup.Name},
        "rating": (
            {
                "quality_score": rating.QualityScore,
                "compliance_score": rating.ComplianceScore,
                "reliability_score": rating.ReliabilityScore,
                "lead_time_days": rating.LeadTimeDays,
                "min_order_qty": rating.MinOrderQty,
                "certifications": rating.Certifications,
                "last_audit_date": rating.LastAuditDate,
                "risk_tier": rating.RiskTier,
            }
            if rating is not None
            else None
        ),
        "procurement": (
            {
                "orders": int(spend.orders or 0),
                "total_spend_usd": float(spend.total_spend or 0.0),
                "on_time_rate": (
                    float(spend.on_time_rate) if spend.on_time_rate is not None else None
                ),
                "quality_pass_rate": (
                    float(spend.quality_pass_rate)
                    if spend.quality_pass_rate is not None
                    else None
                ),
                "first_order": spend.first_order,
                "last_order": spend.last_order,
            }
            if spend is not None
            else None
        ),
        "products_catalogued": int(distinct_products or 0),
        "top_products_by_spend": [
            {
                "product_id": int(p.Id),
                "sku": p.SKU,
                "type": p.Type,
                "orders": int(p.orders),
                "spend_usd": float(p.spend or 0.0),
            }
            for p in top_products
        ],
        "customer_companies": [
            {"id": int(c.Id), "name": c.Name} for c in companies
        ],
    }


_SUPPLIER_SORT_BY = {
    "spend": "COALESCE(agg.total_spend, 0) DESC",
    "orders": "COALESCE(agg.orders, 0) DESC",
    "on_time": "COALESCE(agg.on_time_rate, 0) DESC",
    "quality": "COALESCE(sr.QualityScore, 0) DESC",
    "reliability": "COALESCE(sr.ReliabilityScore, 0) DESC",
    "compliance": "COALESCE(sr.ComplianceScore, 0) DESC",
    "lead_time": "COALESCE(sr.LeadTimeDays, 9999) ASC",
    "name": "s.Name ASC",
}


def tool_list_suppliers(
    engine: Engine,
    *,
    sort_by: str = "spend",
    risk_tier: str | None = None,
    min_quality: float | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Return a ranked supplier roster with rating + spend metrics.

    Parameters
    ----------
    sort_by : one of ``spend``, ``orders``, ``on_time``, ``quality``,
        ``reliability``, ``compliance``, ``lead_time``, ``name``.
    risk_tier : optional ``Supplier_Rating.RiskTier`` filter (e.g. ``low``).
    min_quality : optional lower bound on ``Supplier_Rating.QualityScore``.
    limit : capped at 50 to keep payload small for voice responses.
    """

    order_clause = _SUPPLIER_SORT_BY.get(sort_by)
    if order_clause is None:
        return {
            "error": "invalid_sort_by",
            "valid": sorted(_SUPPLIER_SORT_BY.keys()),
        }
    limit = max(1, min(50, int(limit)))

    where_clauses: list[str] = []
    params: dict[str, Any] = {}
    if risk_tier:
        where_clauses.append("LOWER(sr.RiskTier) = :rt")
        params["rt"] = risk_tier.lower()
    if min_quality is not None:
        where_clauses.append("sr.QualityScore >= :mq")
        params["mq"] = float(min_quality)
    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    sql = f"""
        WITH agg AS (
            SELECT
                SupplierId,
                COUNT(*)             AS orders,
                SUM(TotalCost)       AS total_spend,
                AVG(OnTime)          AS on_time_rate,
                AVG(QualityPassRate) AS quality_pass_rate
            FROM Procurement_History
            GROUP BY SupplierId
        )
        SELECT
            s.Id                    AS id,
            s.Name                  AS name,
            sr.QualityScore         AS quality,
            sr.ComplianceScore      AS compliance,
            sr.ReliabilityScore     AS reliability,
            sr.LeadTimeDays         AS lead_time_days,
            sr.RiskTier             AS risk_tier,
            sr.Certifications       AS certifications,
            agg.orders              AS orders,
            agg.total_spend         AS total_spend,
            agg.on_time_rate        AS on_time_rate,
            agg.quality_pass_rate   AS quality_pass_rate
        FROM Supplier s
        LEFT JOIN Supplier_Rating sr ON sr.SupplierId = s.Id
        LEFT JOIN agg                ON agg.SupplierId = s.Id
        {where_sql}
        ORDER BY {order_clause}
        LIMIT :limit
    """
    params["limit"] = limit

    try:
        with engine.connect() as conn:
            rows = conn.execute(text(sql), params).fetchall()
    except Exception as exc:  # noqa: BLE001
        return {"error": f"list_suppliers_failed: {exc}"}

    def _f(v: Any) -> Any:
        return float(v) if isinstance(v, (int, float)) and v is not None else v

    return {
        "sort_by": sort_by,
        "risk_tier": risk_tier,
        "min_quality": min_quality,
        "total": len(rows),
        "suppliers": [
            {
                "id": int(r.id),
                "name": r.name,
                "quality_score": _f(r.quality),
                "compliance_score": _f(r.compliance),
                "reliability_score": _f(r.reliability),
                "lead_time_days": r.lead_time_days,
                "risk_tier": r.risk_tier,
                "certifications": r.certifications,
                "orders": int(r.orders) if r.orders is not None else 0,
                "total_spend_usd": (
                    float(r.total_spend) if r.total_spend is not None else 0.0
                ),
                "on_time_rate": _f(r.on_time_rate),
                "quality_pass_rate": _f(r.quality_pass_rate),
            }
            for r in rows
        ],
    }


__all__ = [
    "SQLGuardError",
    "tool_analyze_bom",
    "tool_execute_sql",
    "tool_find_candidates",
    "tool_get_evidence",
    "tool_get_recommendation",
    "tool_get_risks",
    "tool_get_supplier_profile",
    "tool_list_suppliers",
]
