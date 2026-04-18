"""Repeated raw materials and supplier fragmentation metrics."""

from __future__ import annotations

import pandas as pd
from sqlalchemy.engine import Engine

from agnes.data import queries
from agnes.models.reports import (
    ConcentrationNote,
    EntityCounts,
    Phase1Report,
    RepeatedMaterial,
    SupplierFragmentation,
)


def classify_concentration(supplier_count: int) -> ConcentrationNote:
    """Map supplier fan-out to a coarse label (deterministic, not regulatory advice)."""
    if supplier_count <= 1:
        return "single-sourced"
    if supplier_count <= 4:
        return "fragmented"
    return "well-distributed"


def compute_repeated_materials(engine: Engine, min_companies: int = 2) -> list[RepeatedMaterial]:
    """Raw materials appearing in BOMs across at least `min_companies` distinct companies."""
    usage = queries.raw_material_usage(engine)
    suppliers = queries.raw_material_suppliers(engine)
    right = suppliers.drop(columns=["SKU"], errors="ignore")
    merged = usage.merge(right, left_on="RawId", right_on="ProductId", how="left")
    out: list[RepeatedMaterial] = []
    for _, row in merged.iterrows():
        n_companies = int(row["n_companies"])
        if n_companies < min_companies:
            continue
        rid = int(row["RawId"])
        sc = row.get("supplier_count")
        supplier_count = int(sc) if pd.notna(sc) else 0
        raw_ids = row.get("supplier_ids")
        supplier_ids = [int(x) for x in raw_ids] if isinstance(raw_ids, list) else []

        out.append(
            RepeatedMaterial(
                raw_product_id=rid,
                sku=str(row["SKU"]),
                n_boms=int(row["n_boms"]),
                n_finished_goods=int(row["n_finished_goods"]),
                n_companies=n_companies,
                supplier_count=supplier_count,
                supplier_ids=supplier_ids,
            )
        )

    out.sort(key=lambda m: (-m.n_companies, -m.n_boms, m.sku))
    return out


def compute_supplier_fragmentation(
    engine: Engine,
    min_suppliers: int = 2,
) -> list[SupplierFragmentation]:
    """Raw materials offered by at least `min_suppliers` distinct suppliers."""
    sp = queries.raw_material_suppliers(engine)
    usage = queries.raw_material_usage(engine)
    u = usage[["RawId", "n_finished_goods"]].rename(columns={"RawId": "ProductId"})
    merged = sp.merge(u, on="ProductId", how="left")

    out: list[SupplierFragmentation] = []
    for _, row in merged.iterrows():
        sc = int(row["supplier_count"])
        if sc < min_suppliers:
            continue
        pid = int(row["ProductId"])
        nfg = row.get("n_finished_goods")
        n_fg = int(nfg) if pd.notna(nfg) else 0
        names = list(row["supplier_names"])
        out.append(
            SupplierFragmentation(
                raw_product_id=pid,
                sku=str(row["SKU"]),
                supplier_count=sc,
                supplier_names=[str(n) for n in names],
                n_finished_goods_using=n_fg,
                concentration_note=classify_concentration(sc),
            )
        )

    out.sort(key=lambda x: (-x.supplier_count, -x.n_finished_goods_using, x.sku))
    return out


def build_phase1_report(engine: Engine) -> Phase1Report:
    """Assemble entity counts, repeated materials, and supplier fragmentation."""
    ec_df = queries.entity_counts(engine)
    r = ec_df.iloc[0].to_dict()
    entity_counts = EntityCounts(
        Company=int(r["Company"]),
        Product=int(r["Product"]),
        FinishedGood=int(r["FinishedGood"]),
        RawMaterial=int(r["RawMaterial"]),
        BOM=int(r["BOM"]),
        BOM_Component=int(r["BOM_Component"]),
        Supplier=int(r["Supplier"]),
        Supplier_Product=int(r["Supplier_Product"]),
    )
    repeated = compute_repeated_materials(engine, min_companies=2)
    frag = compute_supplier_fragmentation(engine, min_suppliers=2)
    return Phase1Report(
        entity_counts=entity_counts,
        repeated_materials=repeated,
        supplier_fragmentation=frag,
        top_repeated_materials_preview=repeated[:5],
        top_supplier_fragmentation_preview=frag[:5],
    )
