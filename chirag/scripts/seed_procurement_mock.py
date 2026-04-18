#!/usr/bin/env python3
"""Seed deterministic mock procurement data.

Port (not copy) of ``taim/generate_mock_data.py`` adapted to chirag's
``Settings``/``db_loader`` conventions. All mutations run inside a single
SQLite transaction; default mode is ``--dry-run`` which only prints a summary.

Run with::

    uv run python chirag/scripts/seed_procurement_mock.py --apply

Flags
-----
``--apply``       Actually write changes (without this, the script is a no-op).
``--reset``       Drop and recreate the three procurement tables even if they
                  contain data. Implies ``--apply``.
``--force``       Regenerate data even if tables already have rows. Implies
                  ``--apply``.
``--summary``     Path to the JSON summary artifact (default:
                  ``outputs/reports/procurement_seed_summary.json``).
``--seed``        Random seed (default: 42; matches taim).
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from agnes.config.settings import Settings

CATEGORY_PRICES: dict[str, tuple[float, float]] = {
    "protein": (15, 60),
    "sweetener": (2, 20),
    "emulsifier": (8, 35),
    "vitamin": (40, 250),
    "mineral": (5, 45),
    "fiber": (4, 18),
    "fat_oil": (3, 15),
    "flavor": (20, 120),
    "thickener_stabilizer": (6, 30),
    "preservative": (8, 40),
    "acid": (3, 15),
    "color": (25, 150),
    "botanical": (30, 180),
    "capsule_coating": (10, 50),
    "excipient": (2, 12),
    "probiotic": (80, 350),
    "salt_electrolyte": (1, 10),
    "other": (5, 40),
}

FUNCTIONAL_CATEGORIES: dict[str, tuple[str, ...]] = {
    "protein": (
        "protein", "collagen", "peptide", "casein", "whey", "bcaa",
        "l-leucine", "l-isoleucine", "l-valine", "leucine", "amino-acid",
    ),
    "sweetener": (
        "sugar", "stevia", "monk-fruit", "erythritol", "sucralose", "sucrose",
        "fructose", "dextrose", "maltodextrin", "sorbitol", "agave",
        "coconut-sugar", "cane-sugar", "rebaudioside", "acesulfame",
        "tapioca-syrup", "polydextrose", "inulin",
    ),
    "emulsifier": ("lecithin", "polysorbate", "glyceride", "acetoglyceride"),
    "vitamin": (
        "vitamin", "ascorbic", "retinol", "tocopherol", "thiamin", "riboflavin",
        "niacin", "niacinamide", "folate", "folic", "biotin", "cobalamin",
        "cyanocobalamin", "pantothen", "pyridoxine", "cholecalciferol",
        "phytonadione", "menaquinone", "retinyl", "ascorbyl", "beta-carotene",
        "tocopherols",
    ),
    "mineral": (
        "calcium", "magnesium", "zinc", "iron", "selenium", "chromium",
        "copper", "manganese", "potassium", "phosphorus", "iodine", "boron",
        "molybdenum", "ferrous", "cupric", "trace-mineral",
    ),
    "fiber": (
        "fiber", "fibre", "inulin", "psyllium", "prebiotic",
        "fructooligosaccharide", "tapioca-fiber",
    ),
    "fat_oil": (
        "oil", "mct", "coconut-mct", "medium-chain-triglyceride", "safflower",
        "soybean-oil", "corn-oil", "palm-oil",
    ),
    "flavor": (
        "flavor", "flavour", "vanilla", "chocolate", "cocoa", "cinnamon",
        "cherry", "strawberry", "peach", "lemon", "ginger",
    ),
    "thickener_stabilizer": (
        "gum", "starch", "pectin", "agar", "carrageenan", "gelatin", "gellan",
        "xanthan", "cellulose-gum", "acacia", "gum-arabic",
    ),
    "preservative": (
        "benzoate", "sorbate", "sorbic-acid", "bht", "rosemary-extract",
    ),
    "acid": (
        "citric-acid", "malic-acid", "lactic-acid", "tartaric-acid",
        "stearic-acid",
    ),
    "color": (
        "color", "lake", "caramel", "annatto", "turmeric", "beet-extract",
        "titanium-dioxide", "blue-2", "red-40",
    ),
    "botanical": (
        "extract", "herb", "rhodiola", "ashwagandha", "green-tea",
        "grape-seed", "pomegranate", "astaxanthin", "lutein", "lycopene",
        "resveratrol", "coenzyme", "coq10", "taurine",
    ),
    "capsule_coating": (
        "capsule", "coating", "softgel", "hypromellose", "hpmc",
        "hydroxypropyl", "pharmaceutical-glaze", "carnauba-wax", "zein",
        "croscarmellose", "plantgel",
    ),
    "excipient": (
        "microcrystalline-cellulose", "cellulose", "silica", "silicon-dioxide",
        "magnesium-stearate", "talc", "dicalcium-phosphate",
        "tricalcium-phosphate", "rice-flour", "rice-powder",
        "modified-cellulose", "sodium-alginate",
    ),
    "probiotic": ("probiotic", "bifidobacterium", "lactobacillus", "ferment"),
    "salt_electrolyte": (
        "salt", "sodium-chloride", "himalayan", "sea-salt", "chloride",
        "dipotassium-phosphate", "potassium-chloride", "sodium-citrate",
    ),
}

ALL_CERTS: tuple[str, ...] = (
    "GMP", "ISO-9001", "ISO-22000", "FSSC-22000", "organic", "non-GMO",
    "kosher", "halal", "NSF", "USP-verified",
)


def _base_name(sku: str) -> str:
    s = re.sub(r"^RM-C\d+-", "", sku)
    s = re.sub(r"-[0-9a-f]{6,}$", "", s, flags=re.IGNORECASE)
    return s.lower().strip("-")


def _categorize(name: str) -> str:
    name_lower = name.lower()
    scores: dict[str, int] = {}
    for cat, keywords in FUNCTIONAL_CATEGORIES.items():
        for kw in keywords:
            if kw in name_lower:
                scores[cat] = scores.get(cat, 0) + len(kw)
    if scores:
        return max(scores, key=lambda k: scores[k])
    return "other"


def _table_has_rows(cur: sqlite3.Cursor, table: str) -> int:
    try:
        return int(cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    except sqlite3.OperationalError:
        return 0


def _drop_tables(cur: sqlite3.Cursor) -> None:
    cur.execute("DROP TABLE IF EXISTS Procurement_History")
    cur.execute("DROP TABLE IF EXISTS Price_Benchmark")
    cur.execute("DROP TABLE IF EXISTS Supplier_Rating")


def _create_tables(cur: sqlite3.Cursor) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS Supplier_Rating (
            SupplierId INTEGER PRIMARY KEY REFERENCES Supplier(Id),
            QualityScore REAL,
            ComplianceScore REAL,
            ReliabilityScore REAL,
            LeadTimeDays INTEGER,
            MinOrderQty INTEGER,
            Certifications TEXT,
            LastAuditDate TEXT,
            RiskTier TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS Procurement_History (
            Id INTEGER PRIMARY KEY AUTOINCREMENT,
            SupplierId INTEGER REFERENCES Supplier(Id),
            ProductId INTEGER REFERENCES Product(Id),
            CompanyId INTEGER REFERENCES Company(Id),
            OrderDate TEXT,
            DeliveryDate TEXT,
            Quantity REAL,
            UnitPrice REAL,
            TotalCost REAL,
            Currency TEXT DEFAULT 'USD',
            OnTime INTEGER,
            QualityPassRate REAL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS Price_Benchmark (
            BaseName TEXT PRIMARY KEY,
            AvgMarketPrice REAL,
            MinPrice REAL,
            MaxPrice REAL,
            PriceVolatility REAL,
            LastUpdated TEXT
        )
        """
    )


def _generate_supplier_ratings(
    cur: sqlite3.Cursor,
    suppliers: dict[int, dict[str, object]],
    supplier_to_products: dict[int, list[int]],
    rng: random.Random,
) -> dict[int, dict[str, object]]:
    profiles: dict[int, dict[str, object]] = {}
    for sid in suppliers:
        product_count = len(supplier_to_products.get(sid, []))
        size_factor = min(product_count / 100, 1.0)

        quality = max(50, min(100, rng.gauss(82 + size_factor * 8, 8)))
        compliance = max(55, min(100, rng.gauss(85 + size_factor * 5, 7)))
        reliability = max(60, min(100, rng.gauss(88 + size_factor * 5, 6)))

        lead_time = max(5, int(rng.gauss(28 - size_factor * 10, 12)))
        moq = rng.choice([50, 100, 250, 500, 1000, 2500, 5000])

        n_certs = max(1, int(rng.gauss(3 + size_factor * 3, 1.5)))
        certs = ["GMP"]
        remaining = [c for c in ALL_CERTS if c != "GMP"]
        rng.shuffle(remaining)
        certs.extend(remaining[: n_certs - 1])

        days_ago = rng.randint(30, 540)
        audit_date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")

        composite = quality * 0.35 + compliance * 0.35 + reliability * 0.3
        if composite >= 88:
            risk_tier = "low"
        elif composite >= 75:
            risk_tier = "medium"
        else:
            risk_tier = "high"

        profile = {
            "quality": round(quality, 1),
            "compliance": round(compliance, 1),
            "reliability": round(reliability, 1),
            "lead_time": lead_time,
            "moq": moq,
            "certs": ",".join(sorted(certs)),
            "audit_date": audit_date,
            "risk_tier": risk_tier,
        }
        profiles[sid] = profile

        cur.execute(
            """
            INSERT INTO Supplier_Rating
            (SupplierId, QualityScore, ComplianceScore, ReliabilityScore,
             LeadTimeDays, MinOrderQty, Certifications, LastAuditDate, RiskTier)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sid, profile["quality"], profile["compliance"],
                profile["reliability"], profile["lead_time"], profile["moq"],
                profile["certs"], profile["audit_date"], profile["risk_tier"],
            ),
        )
    return profiles


def _generate_price_benchmarks(
    cur: sqlite3.Cursor,
    base_name_map: dict[str, list[int]],
    rng: random.Random,
) -> dict[str, dict[str, float]]:
    prices: dict[str, dict[str, float]] = {}
    for bn in base_name_map:
        cat = _categorize(bn)
        price_range = CATEGORY_PRICES.get(cat, (5.0, 40.0))
        base_price = rng.uniform(*price_range)
        volatility = rng.uniform(0.05, 0.35)
        min_price = base_price * (1 - volatility)
        max_price = base_price * (1 + volatility)
        avg_price = base_price * rng.uniform(0.95, 1.05)
        entry = {
            "avg": round(avg_price, 2),
            "min": round(min_price, 2),
            "max": round(max_price, 2),
            "volatility": round(volatility, 3),
        }
        prices[bn] = entry
        cur.execute(
            """
            INSERT INTO Price_Benchmark (BaseName, AvgMarketPrice, MinPrice,
                                          MaxPrice, PriceVolatility, LastUpdated)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                bn, entry["avg"], entry["min"], entry["max"],
                entry["volatility"], "2026-04-01",
            ),
        )
    return prices


def _generate_procurement_history(
    cur: sqlite3.Cursor,
    rm_products: dict[int, dict[str, object]],
    supplier_products: list[tuple[int, int]],
    product_companies: dict[int, set[int]],
    ingredient_prices: dict[str, dict[str, float]],
    supplier_profiles: dict[int, dict[str, object]],
    rng: random.Random,
) -> int:
    start_date = datetime(2024, 4, 1)
    end_date = datetime(2026, 4, 1)
    total_days = (end_date - start_date).days
    order_count = 0

    for sid, pid in supplier_products:
        if pid not in rm_products:
            continue
        bn = _base_name(str(rm_products[pid]["SKU"]))
        if bn not in ingredient_prices:
            continue
        base_price = ingredient_prices[bn]["avg"]
        vol = ingredient_prices[bn]["volatility"]
        sup_profile = supplier_profiles[sid]

        cos = product_companies.get(pid, set())
        if not cos:
            cos = {int(rm_products[pid]["CompanyId"])}

        for cid in cos:
            n_orders = rng.randint(2, 8)
            for _ in range(n_orders):
                order_day = rng.randint(0, total_days - 30)
                order_date = start_date + timedelta(days=order_day)
                qty = sup_profile["moq"] * rng.choice([1, 1, 1, 2, 2, 3, 5])

                quality_premium = (float(sup_profile["quality"]) - 80) / 100 * 0.1
                price_variation = rng.gauss(0, vol * 0.5)
                unit_price = base_price * (1 + quality_premium + price_variation)
                unit_price = max(base_price * 0.5, unit_price)

                total_cost = qty * unit_price
                actual_lead = max(
                    1,
                    int(rng.gauss(
                        float(sup_profile["lead_time"]),
                        float(sup_profile["lead_time"]) * 0.2,
                    )),
                )
                delivery_date = order_date + timedelta(days=actual_lead)
                on_time_prob = float(sup_profile["reliability"]) / 100
                on_time = 1 if rng.random() < on_time_prob else 0
                qpr = max(70, min(100, rng.gauss(
                    float(sup_profile["quality"]) * 0.95 + 5, 3,
                )))

                cur.execute(
                    """
                    INSERT INTO Procurement_History
                    (SupplierId, ProductId, CompanyId, OrderDate, DeliveryDate,
                     Quantity, UnitPrice, TotalCost, Currency, OnTime,
                     QualityPassRate)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'USD', ?, ?)
                    """,
                    (
                        sid, pid, cid,
                        order_date.strftime("%Y-%m-%d"),
                        delivery_date.strftime("%Y-%m-%d"),
                        round(qty, 1), round(unit_price, 2),
                        round(total_cost, 2), on_time, round(qpr, 1),
                    ),
                )
                order_count += 1
    return order_count


def _build_summary(
    cur: sqlite3.Cursor,
    applied: bool,
    reset: bool,
) -> dict[str, object]:
    def _count(table: str) -> int:
        try:
            return int(cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        except sqlite3.OperationalError:
            return 0

    total_spend = 0.0
    on_time_rate = 0.0
    if _count("Procurement_History") > 0:
        total_spend = float(
            cur.execute("SELECT SUM(TotalCost) FROM Procurement_History").fetchone()[0] or 0
        )
        on_time_rate = float(
            cur.execute("SELECT AVG(OnTime)*100 FROM Procurement_History").fetchone()[0] or 0
        )

    risk_rows = cur.execute(
        "SELECT RiskTier, COUNT(*) FROM Supplier_Rating GROUP BY RiskTier"
    ).fetchall() if _count("Supplier_Rating") > 0 else []
    risk_dist = {str(t): int(c) for t, c in risk_rows}

    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "applied": applied,
        "reset": reset,
        "counts": {
            "Supplier_Rating": _count("Supplier_Rating"),
            "Price_Benchmark": _count("Price_Benchmark"),
            "Procurement_History": _count("Procurement_History"),
        },
        "total_spend_usd": round(total_spend, 2),
        "on_time_rate_pct": round(on_time_rate, 2),
        "risk_distribution": risk_dist,
        "schema_version": "v1",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write changes.")
    parser.add_argument(
        "--reset", action="store_true",
        help="Drop+recreate the three procurement tables. Implies --apply.",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Regenerate even if tables already populated. Implies --apply.",
    )
    parser.add_argument(
        "--summary", type=Path,
        default=Path("outputs/reports/procurement_seed_summary.json"),
        help="Path for the JSON summary artifact.",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    args = parser.parse_args(argv)

    if args.reset or args.force:
        args.apply = True

    settings = Settings()
    db_path: Path = settings.db_path.resolve()
    if not db_path.is_file():
        print(json.dumps({"ok": False, "error": f"db not found: {db_path}"}))
        return 1

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    rng = random.Random(args.seed)

    pre_counts = {t: _table_has_rows(cur, t) for t in (
        "Supplier_Rating", "Price_Benchmark", "Procurement_History",
    )}

    if not args.apply:
        summary = {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "applied": False,
            "reset": False,
            "pre_counts": pre_counts,
            "note": "dry-run; pass --apply to write.",
        }
        print(json.dumps(summary, indent=2))
        conn.close()
        return 0

    already_populated = all(v > 0 for v in pre_counts.values())
    if already_populated and not (args.force or args.reset):
        summary = _build_summary(cur, applied=False, reset=False)
        summary["note"] = (
            "tables already populated; pass --force or --reset to rebuild."
        )
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(json.dumps(summary, indent=2))
        print(json.dumps(summary, indent=2))
        conn.close()
        return 0

    try:
        if args.reset or already_populated:
            _drop_tables(cur)
        _create_tables(cur)

        suppliers = {r["Id"]: dict(r) for r in cur.execute("SELECT * FROM Supplier")}
        products = {r["Id"]: dict(r) for r in cur.execute("SELECT * FROM Product")}
        supplier_products = [
            (r["SupplierId"], r["ProductId"])
            for r in cur.execute("SELECT SupplierId, ProductId FROM Supplier_Product")
        ]

        rm_products = {
            pid: p for pid, p in products.items() if p["Type"] == "raw-material"
        }
        base_name_map: dict[str, list[int]] = {}
        for pid, p in rm_products.items():
            bn = _base_name(str(p["SKU"]))
            if bn:
                base_name_map.setdefault(bn, []).append(pid)

        supplier_to_products: dict[int, list[int]] = defaultdict(list)
        for sid, pid in supplier_products:
            supplier_to_products[sid].append(pid)

        bom_components = list(
            cur.execute("SELECT BOMId, ConsumedProductId FROM BOM_Component")
        )
        boms = {
            r["Id"]: r["ProducedProductId"]
            for r in cur.execute("SELECT Id, ProducedProductId FROM BOM")
        }
        product_companies: dict[int, set[int]] = defaultdict(set)
        for row in bom_components:
            fg_id = boms.get(row["BOMId"])
            if fg_id and fg_id in products:
                product_companies[row["ConsumedProductId"]].add(
                    int(products[fg_id]["CompanyId"])
                )

        supplier_profiles = _generate_supplier_ratings(
            cur, suppliers, supplier_to_products, rng,
        )
        ingredient_prices = _generate_price_benchmarks(cur, base_name_map, rng)
        _generate_procurement_history(
            cur, rm_products, supplier_products, product_companies,
            ingredient_prices, supplier_profiles, rng,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        raise

    summary = _build_summary(cur, applied=True, reset=args.reset)
    summary["pre_counts"] = pre_counts
    conn.close()

    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
