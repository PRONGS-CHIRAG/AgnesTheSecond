#!/usr/bin/env python3
"""In-place upgrade of ``outputs/reports/substitute_candidates.json`` to v2.

Adds ``substitution_type`` and ``type_confidence`` to each candidate without
running the embedding pipeline (no OpenAI calls). Derivation follows the same
rule implemented in ``candidate_generator.classify_substitution_type``:

- identical keys -> direct/1.0 (shouldn't occur; Phase 4 excludes self pairs)
- same family + lexical_sim >= 0.4 -> variant/0.75
- same family only -> functional/0.5
- different family -> functional/0.25
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from agnes.models.substitutes import SUBSTITUTES_SCHEMA_VERSION


def _classify(source_key: str, candidate_key: str, feats: dict) -> tuple[str, float]:
    if source_key == candidate_key:
        return "direct", 1.0
    family_match = bool(feats.get("family_match"))
    lex = float(feats.get("lexical_sim") or 0.0)
    if family_match and lex >= 0.4:
        return "variant", 0.75
    if family_match:
        return "functional", 0.5
    return "functional", 0.25


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--path",
        type=Path,
        default=Path("outputs/reports/substitute_candidates.json"),
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if not args.path.is_file():
        print(json.dumps({"ok": False, "error": f"not found: {args.path}"}))
        return 1

    data = json.loads(args.path.read_text())
    cands = data.get("candidates", [])
    n_migrated = 0
    counts: dict[str, int] = {}
    for cand in cands:
        sub_type, sub_conf = _classify(
            cand.get("source_key", ""),
            cand.get("candidate_key", ""),
            cand.get("features", {}) or {},
        )
        if "substitution_type" not in cand or "type_confidence" not in cand:
            n_migrated += 1
        cand["substitution_type"] = sub_type
        cand["type_confidence"] = sub_conf
        cand["schema_version"] = SUBSTITUTES_SCHEMA_VERSION
        counts[sub_type] = counts.get(sub_type, 0) + 1

    data["schema_version"] = SUBSTITUTES_SCHEMA_VERSION

    if args.dry_run:
        print(json.dumps({
            "ok": True, "dry_run": True, "target_version": SUBSTITUTES_SCHEMA_VERSION,
            "n_candidates": len(cands), "n_migrated": n_migrated, "type_counts": counts,
        }, indent=2))
        return 0

    args.path.write_text(json.dumps(data, indent=2))

    csv_path = args.path.with_suffix(".csv")
    if csv_path.is_file() and cands:
        import csv

        sample = cands[0]
        feat_keys = sorted((sample.get("features") or {}).keys())
        base_keys = [
            k for k in sample
            if k not in {"features"}
        ]
        fieldnames = base_keys + [f"feat_{k}" for k in feat_keys]
        with csv_path.open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for c in cands:
                row = {k: c.get(k, "") for k in base_keys}
                if isinstance(row.get("roles"), list):
                    row["roles"] = json.dumps(row["roles"])
                feats = c.get("features", {}) or {}
                for k in feat_keys:
                    v = feats.get(k)
                    if isinstance(v, list):
                        v = json.dumps(v)
                    row[f"feat_{k}"] = v if v is not None else ""
                writer.writerow(row)

    print(json.dumps({
        "ok": True, "dry_run": False, "target_version": SUBSTITUTES_SCHEMA_VERSION,
        "n_candidates": len(cands), "n_migrated": n_migrated, "type_counts": counts,
    }, indent=2))
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
