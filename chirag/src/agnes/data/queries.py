"""Read-only relational queries over the challenge SQLite schema."""

from __future__ import annotations

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine


def load_companies(engine: Engine) -> pd.DataFrame:
    """Load all Company rows."""
    return pd.read_sql_table("Company", engine)


def load_products(engine: Engine) -> pd.DataFrame:
    """Load all Product rows (finished-good and raw-material)."""
    return pd.read_sql_table("Product", engine)


def load_boms(engine: Engine) -> pd.DataFrame:
    """Load BOM rows (Id, ProducedProductId)."""
    return pd.read_sql_table("BOM", engine)


def load_bom_components(engine: Engine) -> pd.DataFrame:
    """Load BOM_Component rows."""
    return pd.read_sql_table("BOM_Component", engine)


def load_suppliers(engine: Engine) -> pd.DataFrame:
    """Load Supplier rows."""
    return pd.read_sql_table("Supplier", engine)


def load_supplier_products(engine: Engine) -> pd.DataFrame:
    """Load Supplier_Product rows."""
    return pd.read_sql_table("Supplier_Product", engine)


def raw_material_usage(engine: Engine) -> pd.DataFrame:
    """
    Per raw-material product: how many BOMs, finished goods, and companies use it.

    Columns: RawId, SKU, n_boms, n_finished_goods, n_companies
    """
    sql = text("""
        SELECT
            pr.Id AS RawId,
            pr.SKU AS SKU,
            COUNT(DISTINCT bc.BOMId) AS n_boms,
            COUNT(DISTINCT b.ProducedProductId) AS n_finished_goods,
            COUNT(DISTINCT pfg.CompanyId) AS n_companies
        FROM BOM_Component bc
        JOIN BOM b ON b.Id = bc.BOMId
        JOIN Product pfg ON pfg.Id = b.ProducedProductId AND pfg.Type = 'finished-good'
        JOIN Product pr ON pr.Id = bc.ConsumedProductId AND pr.Type = 'raw-material'
        GROUP BY pr.Id, pr.SKU
    """)
    with engine.connect() as conn:
        return pd.read_sql(sql, conn)


def raw_material_suppliers(engine: Engine) -> pd.DataFrame:
    """
    Per raw-material: supplier ids, names, and counts.

    Columns: ProductId, SKU, supplier_count, supplier_ids, supplier_names
    """
    sql = text("""
        SELECT
            p.Id AS ProductId,
            p.SKU AS SKU,
            sp.SupplierId,
            s.Name AS SupplierName
        FROM Product p
        JOIN Supplier_Product sp ON sp.ProductId = p.Id
        JOIN Supplier s ON s.Id = sp.SupplierId
        WHERE p.Type = 'raw-material'
        ORDER BY p.Id, sp.SupplierId
    """)
    with engine.connect() as conn:
        df = pd.read_sql(sql, conn)
    if df.empty:
        return pd.DataFrame(
            columns=["ProductId", "SKU", "supplier_count", "supplier_ids", "supplier_names"]
        )

    out_rows: list[dict] = []
    for product_id, g in df.groupby("ProductId", sort=True):
        ids = g["SupplierId"].astype(int).tolist()
        names = g["SupplierName"].astype(str).tolist()
        out_rows.append(
            {
                "ProductId": int(product_id),
                "SKU": str(g["SKU"].iloc[0]),
                "supplier_count": len(ids),
                "supplier_ids": ids,
                "supplier_names": names,
            }
        )
    return pd.DataFrame(out_rows)


def company_product_tree(engine: Engine) -> pd.DataFrame:
    """
    Company -> finished good -> BOM -> raw material (one row per BOM line).

    Columns: CompanyId, CompanyName, FinishedProductId, FinishedSKU, BOMId,
             RawProductId, RawSKU
    """
    sql = text("""
        SELECT
            c.Id AS CompanyId,
            c.Name AS CompanyName,
            pfg.Id AS FinishedProductId,
            pfg.SKU AS FinishedSKU,
            b.Id AS BOMId,
            pr.Id AS RawProductId,
            pr.SKU AS RawSKU
        FROM Company c
        JOIN Product pfg ON pfg.CompanyId = c.Id AND pfg.Type = 'finished-good'
        JOIN BOM b ON b.ProducedProductId = pfg.Id
        JOIN BOM_Component bc ON bc.BOMId = b.Id
        JOIN Product pr ON pr.Id = bc.ConsumedProductId AND pr.Type = 'raw-material'
        ORDER BY c.Id, pfg.Id, pr.Id
    """)
    with engine.connect() as conn:
        return pd.read_sql(sql, conn)


def supplier_products_by_company(engine: Engine) -> pd.DataFrame:
    """
    Per (company, raw-material, supplier): which suppliers serve which companies.

    Derived via: Company -> finished Product -> BOM -> BOM_Component ->
    raw Product -> Supplier_Product. Duplicates are collapsed.

    Columns: CompanyId, SupplierId, RawProductId
    """
    sql = text("""
        SELECT DISTINCT
            pfg.CompanyId AS CompanyId,
            sp.SupplierId AS SupplierId,
            pr.Id AS RawProductId
        FROM Product pfg
        JOIN BOM b ON b.ProducedProductId = pfg.Id
        JOIN BOM_Component bc ON bc.BOMId = b.Id
        JOIN Product pr ON pr.Id = bc.ConsumedProductId AND pr.Type = 'raw-material'
        JOIN Supplier_Product sp ON sp.ProductId = pr.Id
        WHERE pfg.Type = 'finished-good'
        ORDER BY pfg.CompanyId, sp.SupplierId, pr.Id
    """)
    with engine.connect() as conn:
        return pd.read_sql(sql, conn)


def entity_counts(engine: Engine) -> pd.DataFrame:
    """Return a single-row DataFrame with EntityCounts-compatible columns."""
    sql = text("""
        SELECT
            (SELECT COUNT(*) FROM Company) AS Company,
            (SELECT COUNT(*) FROM Product) AS Product,
            (SELECT COUNT(*) FROM Product WHERE Type = 'finished-good') AS FinishedGood,
            (SELECT COUNT(*) FROM Product WHERE Type = 'raw-material') AS RawMaterial,
            (SELECT COUNT(*) FROM BOM) AS BOM,
            (SELECT COUNT(*) FROM BOM_Component) AS BOM_Component,
            (SELECT COUNT(*) FROM Supplier) AS Supplier,
            (SELECT COUNT(*) FROM Supplier_Product) AS Supplier_Product
    """)
    with engine.connect() as conn:
        return pd.read_sql(sql, conn)
