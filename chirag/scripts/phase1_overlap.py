#!/usr/bin/env python3
"""Write entity counts, overlap CSVs, and combined Phase 1 report."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from agnes.config.settings import Settings
from agnes.data.db_loader import get_engine
from agnes.services.overlap import (
    build_phase1_report,
    compute_repeated_materials,
    compute_supplier_fragmentation,
)
from agnes.utils.logging import configure_logging

OUT_DIR = Path("outputs/reports")


def main() -> int:
    settings = Settings()
    configure_logging(settings.log_level)
    engine = get_engine(settings)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    report = build_phase1_report(engine)
    ec = report.entity_counts.model_dump()
    (OUT_DIR / "entity_counts.json").write_text(
        json.dumps(ec, indent=2),
        encoding="utf-8",
    )

    repeated = compute_repeated_materials(engine, min_companies=2)
    rdf = (
        pd.DataFrame([m.model_dump() for m in repeated])
        if repeated
        else pd.DataFrame(
            columns=[
                "raw_product_id",
                "sku",
                "n_boms",
                "n_finished_goods",
                "n_companies",
                "supplier_count",
                "supplier_ids",
            ]
        )
    )
    if not rdf.empty and "supplier_ids" in rdf.columns:
        rdf["supplier_ids"] = rdf["supplier_ids"].apply(json.dumps)
    rdf.to_csv(OUT_DIR / "repeated_raw_materials.csv", index=False)

    frag = compute_supplier_fragmentation(engine, min_suppliers=2)
    fdf = (
        pd.DataFrame([m.model_dump() for m in frag])
        if frag
        else pd.DataFrame(
            columns=[
                "raw_product_id",
                "sku",
                "supplier_count",
                "supplier_names",
                "n_finished_goods_using",
                "concentration_note",
            ]
        )
    )
    if not fdf.empty and "supplier_names" in fdf.columns:
        fdf["supplier_names"] = fdf["supplier_names"].apply(json.dumps)
    fdf.to_csv(OUT_DIR / "supplier_fragmentation.csv", index=False)

    (OUT_DIR / "phase1_report.json").write_text(
        report.model_dump_json(indent=2),
        encoding="utf-8",
    )

    one_line = {
        "ok": True,
        "entity_counts": ec,
        "repeated_materials_total": len(repeated),
        "supplier_fragmentation_total": len(frag),
        "top_repeated_materials": [m.model_dump() for m in report.top_repeated_materials_preview],
        "top_supplier_fragmentation": [
            m.model_dump() for m in report.top_supplier_fragmentation_preview
        ],
    }
    print(json.dumps(one_line, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
