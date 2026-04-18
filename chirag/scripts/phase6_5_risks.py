#!/usr/bin/env python3
"""Phase 6.5: deterministic supply-risk register.

Aggregates raw-material / supplier views into ``IngredientProfile`` objects,
runs the 5 deterministic risk detectors in ``agnes.services.risk``, and writes
``outputs/reports/supply_risks.json`` (cache-keyed on the risk schema + taxonomy
version so downstream phases can invalidate cleanly).

Usage::

    uv run python chirag/scripts/phase6_5_risks.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from agnes.canonicalization.taxonomy import TAXONOMY_VERSION
from agnes.config.settings import Settings
from agnes.data.db_loader import (
    get_engine,
    load_price_benchmarks,
    load_supplier_ratings,
)
from agnes.data.queries import (
    company_product_tree,
    load_suppliers,
    raw_material_suppliers,
)
from agnes.models.risk import RISK_SCHEMA_VERSION, RiskItem, SupplyRiskReport
from agnes.services.risk import (
    IngredientProfile,
    SupplierInfo,
    critical_ingredient_risks,
    price_volatility_risks,
    single_source_risks,
    sort_risks,
    supplier_concentration_risks,
    supplier_quality_risks,
)
from agnes.utils.logging import configure_logging

OUT_DIR = Path("outputs/reports")


def _base_name(sku: str) -> str:
    s = re.sub(r"^RM-C\d+-", "", sku)
    s = re.sub(r"-[0-9a-f]{6,}$", "", s, flags=re.IGNORECASE)
    return s.lower().strip("-")


def _humanize(bn: str) -> str:
    return bn.replace("-", " ").strip().title()


def _build_profiles(settings: Settings) -> tuple[
    list[IngredientProfile],
    dict[int, str],
    dict[int, int],
]:
    engine = get_engine(settings)

    suppliers_df = load_suppliers(engine)
    supplier_names: dict[int, str] = {
        int(row["Id"]): str(row["Name"]) for _, row in suppliers_df.iterrows()
    }

    rms_df = raw_material_suppliers(engine)
    supplier_product_counts: dict[int, int] = defaultdict(int)

    base_groups: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "product_ids": set(),
            "supplier_ids": set(),
            "supplier_names": {},
        }
    )

    for _, row in rms_df.iterrows():
        sku = str(row["SKU"])
        bn = _base_name(sku)
        if not bn:
            continue
        g = base_groups[bn]
        product_ids = g["product_ids"]
        assert isinstance(product_ids, set)
        product_ids.add(int(row["ProductId"]))
        sids = list(row.get("supplier_ids") or [])
        snames = list(row.get("supplier_names") or [])
        supplier_ids = g["supplier_ids"]
        supplier_name_map = g["supplier_names"]
        assert isinstance(supplier_ids, set)
        assert isinstance(supplier_name_map, dict)
        for sid, sname in zip(sids, snames):
            sid_int = int(sid)
            supplier_ids.add(sid_int)
            supplier_name_map[sid_int] = str(sname)
            supplier_product_counts[sid_int] += 1

    tree = company_product_tree(engine)

    product_to_companies: dict[int, set[int]] = defaultdict(set)
    for _, row in tree.iterrows():
        product_to_companies[int(row["RawProductId"])].add(int(row["CompanyId"]))

    profiles: list[IngredientProfile] = []
    for bn, g in base_groups.items():
        product_ids = g["product_ids"]
        supplier_ids = g["supplier_ids"]
        supplier_name_map = g["supplier_names"]
        assert isinstance(product_ids, set)
        assert isinstance(supplier_ids, set)
        assert isinstance(supplier_name_map, dict)

        companies: set[int] = set()
        for pid in product_ids:
            companies.update(product_to_companies.get(pid, set()))

        profiles.append(IngredientProfile(
            base_name=bn,
            label=_humanize(bn),
            suppliers=tuple(
                SupplierInfo(sid, supplier_name_map.get(sid, f"supplier-{sid}"))
                for sid in sorted(supplier_ids)
            ),
            n_companies=len(companies),
            n_products=len(product_ids),
        ))

    return profiles, supplier_names, dict(supplier_product_counts)


def _emit(report: SupplyRiskReport, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report.model_dump_json(indent=2))


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--out",
        type=Path,
        default=OUT_DIR / "supply_risks.json",
        help="Output path for the SupplyRiskReport JSON.",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    settings = Settings()
    configure_logging(settings.log_level)

    try:
        profiles, supplier_names, supplier_product_counts = _build_profiles(settings)
    except FileNotFoundError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1

    engine = get_engine(settings)
    ratings = load_supplier_ratings(engine, settings)
    benchmarks = load_price_benchmarks(engine, settings)

    items: list[RiskItem] = []
    items += single_source_risks(profiles)
    items += supplier_concentration_risks(profiles, supplier_names)
    items += critical_ingredient_risks(profiles)
    items += supplier_quality_risks(
        ratings, supplier_names, supplier_product_counts,
    )
    items += price_volatility_risks(profiles, benchmarks)
    items = sort_risks(items)

    by_severity: dict[str, int] = defaultdict(int)
    by_type: dict[str, int] = defaultdict(int)
    for it in items:
        by_severity[it.severity] += 1
        by_type[it.type] += 1

    report = SupplyRiskReport(
        schema_version=RISK_SCHEMA_VERSION,
        taxonomy_version=TAXONOMY_VERSION,
        generated_at=datetime.now(UTC),
        items=items,
        by_severity=dict(by_severity),
        by_type=dict(by_type),
        n_total=len(items),
        partial=not (ratings or benchmarks),
    )

    _emit(report, args.out)
    print(json.dumps({
        "ok": True,
        "report": str(args.out),
        "n_items": report.n_total,
        "by_severity": report.by_severity,
        "by_type": report.by_type,
        "partial": report.partial,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
