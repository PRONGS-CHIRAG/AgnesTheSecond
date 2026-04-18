#!/usr/bin/env python3
"""Phase 4: generate and persist substitute candidates over the CanonicalRegistry."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from agnes.canonicalization.taxonomy import TAXONOMY_VERSION
from agnes.config.settings import Settings
from agnes.data.db_loader import get_engine
from agnes.graph.builder import build_graph_payload
from agnes.graph.queries import MaterialGraphIndex
from agnes.graph.schema import GRAPH_SCHEMA_VERSION
from agnes.models.canonical import CanonicalRegistry
from agnes.models.substitutes import (
    SUBSTITUTES_SCHEMA_VERSION,
    SubstituteCandidate,
    SubstituteCandidateReport,
    TargetDiagnostics,
)
from agnes.substitutes.candidate_generator import generate_candidates
from agnes.substitutes.embeddings import EmbeddingClient
from agnes.substitutes.scoring import normalize_weights
from agnes.utils.logging import configure_logging

OUT_DIR = Path("outputs/reports")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate Phase 4 substitute candidates.")
    p.add_argument(
        "--registry",
        type=Path,
        default=Path("outputs/reports/canonical_registry.json"),
        help="Path to Phase 2 canonical_registry.json",
    )
    p.add_argument("--target", type=str, default=None, help="Single canonical_key to score.")
    p.add_argument("--all", action="store_true", help="Score every canonical key in the registry.")
    p.add_argument("--top-k", type=int, default=None, help="Override Settings.phase4_top_k.")
    p.add_argument(
        "--min-score", type=float, default=None, help="Override Settings.phase4_min_score."
    )
    p.add_argument(
        "--cross-family",
        action="store_true",
        help="Search outside the source material's IngredientFamily.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip embeddings (no network) and report candidate counts only.",
    )
    p.add_argument(
        "--no-cache",
        action="store_true",
        help="Do not write the embedding cache back to disk.",
    )
    return p.parse_args()


def _weights_from_settings(settings: Settings) -> dict[str, float]:
    try:
        raw = json.loads(settings.phase4_weights)
    except json.JSONDecodeError:
        raw = {}
    return normalize_weights(raw if isinstance(raw, dict) else {})


def main() -> int:
    args = _parse_args()
    settings = Settings()
    configure_logging(settings.log_level)

    if not args.target and not args.all:
        print(
            json.dumps({"error": "must specify --target <key> or --all"}), file=sys.stderr
        )
        return 2

    if not args.registry.is_file():
        print(
            json.dumps({"error": "registry_missing", "path": str(args.registry)}),
            file=sys.stderr,
        )
        return 1
    registry = CanonicalRegistry.model_validate_json(
        args.registry.read_text(encoding="utf-8")
    )
    if registry.taxonomy_version != TAXONOMY_VERSION:
        print(
            json.dumps(
                {
                    "error": "taxonomy_version_mismatch",
                    "expected": TAXONOMY_VERSION,
                    "got": registry.taxonomy_version,
                }
            ),
            file=sys.stderr,
        )
        return 1

    engine = get_engine(settings)
    nodes, edges = build_graph_payload(registry, engine)
    index = MaterialGraphIndex.from_payload(nodes, edges)

    top_k = args.top_k if args.top_k is not None else settings.phase4_top_k
    min_score = (
        args.min_score if args.min_score is not None else settings.phase4_min_score
    )
    cross_family = args.cross_family or settings.phase4_cross_family_default
    weights = _weights_from_settings(settings)

    embeddings: EmbeddingClient | None = None
    if not args.dry_run:
        os.environ.setdefault("AGNES_PHASE4_EMBEDDING_MODEL", settings.phase4_embedding_model)
        embeddings = EmbeddingClient(settings)

    if args.target:
        targets = [args.target]
    else:
        targets = registry.canonical_keys()

    t0 = time.perf_counter()
    all_candidates: list[SubstituteCandidate] = []
    diagnostics: list[TargetDiagnostics] = []
    n_with = 0
    best_scores: list[float] = []

    for key in targets:
        cands, diag = generate_candidates(
            target_key=key,
            registry=registry,
            graph_index=index,
            embeddings=embeddings,
            top_k=top_k,
            min_score=min_score,
            cross_family=cross_family,
            weights=weights,
        )
        diagnostics.append(diag)
        all_candidates.extend(cands)
        if cands:
            n_with += 1
            if diag.best_score is not None:
                best_scores.append(diag.best_score)

    if embeddings is not None and not args.no_cache:
        embeddings.save()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    avg_top_score = sum(best_scores) / len(best_scores) if best_scores else None

    report = SubstituteCandidateReport(
        schema_version=SUBSTITUTES_SCHEMA_VERSION,
        taxonomy_version=TAXONOMY_VERSION,
        graph_schema_version=GRAPH_SCHEMA_VERSION,
        generated_at=datetime.now(UTC),
        embedding_model=embeddings.model if embeddings is not None else None,
        weights=weights,
        min_score=min_score,
        top_k=top_k,
        cross_family=cross_family,
        n_targets=len(targets),
        n_with_candidates=n_with,
        n_without_candidates=len(targets) - n_with,
        avg_top_score=avg_top_score,
        duration_ms=duration_ms,
        partial=False,
        targets=diagnostics,
        candidates=all_candidates,
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / "substitute_candidates.json"
    csv_path = OUT_DIR / "substitute_candidates.csv"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")

    if all_candidates:
        rows = []
        for c in all_candidates:
            d = c.model_dump()
            feats = d.pop("features")
            d.update({f"feat_{k}": v for k, v in feats.items()})
            d["roles"] = json.dumps(d.get("roles", []))
            d["feat_missing_signals"] = json.dumps(d.get("feat_missing_signals", []))
            rows.append(d)
        pd.DataFrame(rows).to_csv(csv_path, index=False)
    else:
        csv_path.write_text("", encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": True,
                "n_targets": report.n_targets,
                "n_with_candidates": report.n_with_candidates,
                "n_without_candidates": report.n_without_candidates,
                "avg_top_score": report.avg_top_score,
                "duration_ms": report.duration_ms,
                "cross_family": report.cross_family,
                "top_k": report.top_k,
                "min_score": report.min_score,
                "report": str(json_path),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
