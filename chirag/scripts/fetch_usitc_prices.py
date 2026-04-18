#!/usr/bin/env python3
"""Fetch USITC DataWeb import prices for ingredients in the HTS crosswalk.

Reads ``data/reference/hts_crosswalk.csv``, hits the DataWeb runReport
endpoint once per unique ``(hts_code, year)``, derives unit values from the
response, and writes two artifacts under ``outputs/reports/``:

- ``ingredient_prices.json`` — full :class:`IngredientPriceReport` payload
- ``ingredient_prices.csv`` — one row per canonical_key for spreadsheet review

Rerunnable: results cache to ``.cache/usitc_prices.json`` keyed by
``(hts_code, year, trade_type, schema_version)``; a second run with warm cache
issues zero API calls.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from agnes.config.settings import Settings
from agnes.tools.usitc_dataweb import (
    PRICE_SCHEMA_VERSION,
    ImportPriceSnapshot,
    PriceCache,
    USITCDataWebClient,
    USITCDataWebError,
)
from agnes.utils.logging import configure_logging, get_logger

OUT_DIR = Path("outputs/reports")
DEFAULT_CROSSWALK = Path("data/reference/hts_crosswalk.csv")

logger = get_logger("fetch_usitc_prices")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--crosswalk", type=Path, default=DEFAULT_CROSSWALK)
    p.add_argument("--year", type=str, default=None, help="Override AGNES_USITC_DEFAULT_YEAR.")
    p.add_argument("--trade-type", type=str, default="Import", choices=["Import", "Export"])
    p.add_argument(
        "--canonical-key",
        type=str,
        default=None,
        help="Optional filter: fetch only rows matching this canonical_key.",
    )
    p.add_argument(
        "--no-cache",
        action="store_true",
        help="Bypass the on-disk cache for this run (still writes on success).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve rows but do not call the DataWeb API.",
    )
    p.add_argument(
        "--out-json",
        type=Path,
        default=OUT_DIR / "ingredient_prices.json",
    )
    p.add_argument(
        "--out-csv",
        type=Path,
        default=OUT_DIR / "ingredient_prices.csv",
    )
    return p.parse_args()


def _load_crosswalk(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"HTS crosswalk not found: {path}")
    rows: list[dict[str, str]] = []
    with path.open() as fh:
        for row in csv.DictReader(fh):
            ck = (row.get("canonical_key") or "").strip()
            hts = (row.get("hts_code") or "").strip()
            if not ck or not hts:
                continue
            rows.append(
                {
                    "canonical_key": ck,
                    "hts_code": hts,
                    "description": (row.get("description") or "").strip(),
                    "notes": (row.get("notes") or "").strip(),
                }
            )
    return rows


def _snapshot_to_row(
    canonical_key: str,
    hts_code: str,
    description: str,
    snapshot: ImportPriceSnapshot | None,
    *,
    error: str | None = None,
) -> dict[str, Any]:
    if snapshot is None:
        return {
            "canonical_key": canonical_key,
            "hts_code": hts_code,
            "description": description,
            "year": None,
            "trade_type": None,
            "customs_value_usd": None,
            "quantity": None,
            "unit_value_usd": None,
            "uom": None,
            "n_countries": 0,
            "error": error,
        }
    return {
        "canonical_key": canonical_key,
        "hts_code": hts_code,
        "description": description,
        "year": snapshot.year,
        "trade_type": snapshot.trade_type,
        "customs_value_usd": snapshot.customs_value_usd,
        "quantity": snapshot.quantity,
        "unit_value_usd": snapshot.unit_value_usd,
        "uom": snapshot.uom,
        "n_countries": len(snapshot.country_breakdown),
        "error": error,
    }


def main() -> int:
    args = _parse_args()
    settings = Settings()
    configure_logging(settings.log_level)

    try:
        crosswalk = _load_crosswalk(args.crosswalk)
    except FileNotFoundError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1

    if args.canonical_key:
        crosswalk = [r for r in crosswalk if r["canonical_key"] == args.canonical_key]
        if not crosswalk:
            print(json.dumps({"ok": False, "error": f"no rows match {args.canonical_key}"}))
            return 1

    year = args.year or settings.usitc_default_year
    trade_type = args.trade_type

    unique_htses = sorted({r["hts_code"] for r in crosswalk})
    by_hts: dict[str, ImportPriceSnapshot | None] = {}
    errors: dict[str, str] = {}

    if args.dry_run:
        logger.info(
            "usitc_dry_run",
            rows=len(crosswalk),
            unique_htses=len(unique_htses),
            year=year,
            trade_type=trade_type,
        )
    else:
        cache = None if args.no_cache else PriceCache(settings.usitc_cache_path)
        try:
            client = USITCDataWebClient(
                api_token=settings.usitc_api_token,
                base_url=settings.usitc_base_url,
                timeout_seconds=settings.usitc_timeout_seconds,
                cache=cache,
            )
        except USITCDataWebError as exc:
            print(json.dumps({"ok": False, "error": str(exc)}))
            return 2

        with client:
            for hts in unique_htses:
                try:
                    snap = client.fetch_snapshot(
                        hts_code=hts,
                        year=year,
                        trade_type=trade_type,
                        use_cache=not args.no_cache,
                    )
                    by_hts[hts] = snap
                except USITCDataWebError as exc:
                    by_hts[hts] = None
                    errors[hts] = str(exc)
                    logger.warning("usitc_fetch_failed", hts=hts, err=str(exc)[:300])

    rows: list[dict[str, Any]] = []
    for entry in crosswalk:
        snap = by_hts.get(entry["hts_code"])
        err = errors.get(entry["hts_code"])
        if args.dry_run and snap is None and err is None:
            err = "dry_run"
        rows.append(
            _snapshot_to_row(
                canonical_key=entry["canonical_key"],
                hts_code=entry["hts_code"],
                description=entry["description"],
                snapshot=snap,
                error=err,
            )
        )

    report = {
        "schema_version": PRICE_SCHEMA_VERSION,
        "generated_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "year": year,
        "trade_type": trade_type,
        "n_rows": len(rows),
        "n_unique_htses": len(unique_htses),
        "n_succeeded": sum(1 for r in rows if r["unit_value_usd"] is not None),
        "n_failed": sum(1 for r in rows if r["error"] is not None),
        "errors": errors,
        "items": rows,
        "snapshots_by_hts": {
            h: (s.model_dump() if s is not None else None) for h, s in by_hts.items()
        },
    }

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(report, indent=2, sort_keys=True))

    df = pd.DataFrame(rows)
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out_csv, index=False)

    summary = {
        "ok": report["n_failed"] == 0 and not args.dry_run,
        "dry_run": args.dry_run,
        "n_rows": report["n_rows"],
        "n_unique_htses": report["n_unique_htses"],
        "n_succeeded": report["n_succeeded"],
        "n_failed": report["n_failed"],
        "out_json": str(args.out_json),
        "out_csv": str(args.out_csv),
    }
    print(json.dumps(summary))
    return 0 if (args.dry_run or report["n_failed"] == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
