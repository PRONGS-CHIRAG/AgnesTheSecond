#!/usr/bin/env python3
"""Upgrade the persisted canonical registry from TAXONOMY_VERSION v1 -> v2.

For every material whose ``ingredient_family == "other"`` we re-run the new
keyword classifier (``classify_family``). Confident v1 assignments are left
untouched; only ``other`` rows are eligible. The registry ``taxonomy_version``
is bumped regardless so downstream phases correctly invalidate their caches.

Usage::

    uv run python chirag/scripts/phase2_upgrade_taxonomy.py [--dry-run]
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from agnes.canonicalization.taxonomy import TAXONOMY_VERSION, classify_family


def _rewrite(materials: list[dict]) -> dict[str, int]:
    stats = {"scanned": 0, "reclassified": 0, "stayed_other": 0, "untouched": 0}
    for mat in materials:
        stats["scanned"] += 1
        fam = mat.get("ingredient_family")
        if fam != "other":
            mat["taxonomy_version"] = TAXONOMY_VERSION
            stats["untouched"] += 1
            continue
        name = (
            mat.get("canonical_key")
            or mat.get("normalized_name")
            or mat.get("sku", "")
        )
        new_fam = classify_family(str(name), default="other")
        mat["taxonomy_version"] = TAXONOMY_VERSION
        if new_fam != "other":
            mat["ingredient_family"] = new_fam
            prev_conf = float(mat.get("confidence") or 0.5)
            mat["confidence"] = min(prev_conf, 0.5)
            stats["reclassified"] += 1
        else:
            stats["stayed_other"] += 1
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json",
        type=Path,
        default=Path("outputs/reports/canonical_registry.json"),
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("outputs/reports/canonical_registry.csv"),
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if not args.json.is_file():
        print(json.dumps({"ok": False, "error": f"not found: {args.json}"}))
        return 1

    data = json.loads(args.json.read_text())
    materials = data.get("materials", [])
    stats = _rewrite(materials)
    data["taxonomy_version"] = TAXONOMY_VERSION

    if args.dry_run:
        print(json.dumps({
            "ok": True, "dry_run": True,
            "target_version": TAXONOMY_VERSION, **stats,
        }, indent=2))
        return 0

    args.json.write_text(json.dumps(data, indent=2))

    if args.csv.is_file() and materials:
        fieldnames = list(materials[0].keys())
        with args.csv.open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for mat in materials:
                writer.writerow({k: mat.get(k, "") for k in fieldnames})

    print(json.dumps({
        "ok": True, "dry_run": False,
        "target_version": TAXONOMY_VERSION, **stats,
    }, indent=2))
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
