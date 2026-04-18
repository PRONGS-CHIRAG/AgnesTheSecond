#!/usr/bin/env python3
"""Phase 5: enrich top Phase 4 substitute candidates with grounded external evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from agnes.config.settings import Settings
from agnes.evidence.enricher import (
    DEFAULT_CACHE_PATH,
    DEFAULT_PROMPT_PATH,
    EvidenceCache,
    enrich_pairs,
    load_prompt_template,
    select_pairs,
)
from agnes.models.canonical import CanonicalRegistry
from agnes.models.substitutes import SubstituteCandidateReport
from agnes.retrieval.openai_grounded import GroundedLLM
from agnes.utils.logging import configure_logging

OUT_DIR = Path("outputs/reports")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run Phase 5 evidence enrichment.")
    p.add_argument(
        "--input",
        type=Path,
        default=Path("outputs/reports/substitute_candidates.json"),
        help="Phase 4 SubstituteCandidateReport to enrich.",
    )
    p.add_argument(
        "--registry",
        type=Path,
        default=Path("outputs/reports/canonical_registry.json"),
        help="Phase 2 CanonicalRegistry for material display names.",
    )
    p.add_argument(
        "--top-sources",
        type=int,
        default=None,
        help="Cap on distinct source materials (default: settings.phase5_top_sources).",
    )
    p.add_argument(
        "--per-source",
        type=int,
        default=None,
        help="Cap on candidates enriched per source (default: settings.phase5_per_source).",
    )
    p.add_argument(
        "--max-total",
        type=int,
        default=None,
        help="Cap on total *new* API calls this run (default: settings.phase5_max_total).",
    )
    p.add_argument(
        "--source",
        type=str,
        default=None,
        help="Restrict enrichment to one source canonical_key.",
    )
    p.add_argument(
        "--model",
        type=str,
        default=None,
        help="Override grounded model id (default: settings.phase5_grounded_model).",
    )
    p.add_argument(
        "--prompt",
        type=Path,
        default=DEFAULT_PROMPT_PATH,
        help="Path to the evidence extraction prompt template.",
    )
    p.add_argument(
        "--cache-path",
        type=Path,
        default=DEFAULT_CACHE_PATH,
        help="Path to the evidence disk cache.",
    )
    p.add_argument(
        "--no-cache",
        action="store_true",
        help="Do not persist the evidence cache back to disk.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Select and print pairs but make zero API calls.",
    )
    return p.parse_args()


def _write_csv(path: Path, report) -> None:
    rows = []
    for item in report.items:
        if not item.claims:
            rows.append(
                {
                    "source_key": item.source_key,
                    "candidate_key": item.candidate_key,
                    "claim_key": None,
                    "polarity": None,
                    "confidence": None,
                    "grounding_strength": None,
                    "value": None,
                    "citations": json.dumps([]),
                    "retrieved_at": item.retrieved_at.isoformat(),
                    "llm_model": item.llm_model,
                }
            )
            continue
        for claim in item.claims:
            rows.append(
                {
                    "source_key": item.source_key,
                    "candidate_key": item.candidate_key,
                    "claim_key": claim.key,
                    "polarity": claim.polarity,
                    "confidence": claim.confidence,
                    "grounding_strength": claim.grounding_strength,
                    "value": claim.value,
                    "citations": json.dumps([c.url for c in claim.citations]),
                    "retrieved_at": item.retrieved_at.isoformat(),
                    "llm_model": item.llm_model,
                }
            )
    if rows:
        pd.DataFrame(rows).to_csv(path, index=False)
    else:
        path.write_text("", encoding="utf-8")


def main() -> int:
    args = _parse_args()
    settings = Settings()
    configure_logging(settings.log_level)

    if not args.input.is_file():
        print(
            json.dumps({"error": "phase4_report_missing", "path": str(args.input)}),
            file=sys.stderr,
        )
        return 1
    if not args.registry.is_file():
        print(
            json.dumps({"error": "registry_missing", "path": str(args.registry)}),
            file=sys.stderr,
        )
        return 1

    report_in = SubstituteCandidateReport.model_validate_json(
        args.input.read_text(encoding="utf-8")
    )
    registry = CanonicalRegistry.model_validate_json(
        args.registry.read_text(encoding="utf-8")
    )

    top_sources = args.top_sources if args.top_sources is not None else settings.phase5_top_sources
    per_source = args.per_source if args.per_source is not None else settings.phase5_per_source
    max_total = args.max_total if args.max_total is not None else settings.phase5_max_total
    model_id = args.model or settings.phase5_grounded_model

    pairs = select_pairs(
        report_in,
        top_sources=top_sources,
        per_source=per_source,
        source_filter=args.source,
    )

    if not pairs:
        print(
            json.dumps(
                {
                    "ok": False,
                    "reason": "no_pairs_selected",
                    "top_sources": top_sources,
                    "per_source": per_source,
                }
            )
        )
        return 0

    template = load_prompt_template(args.prompt)
    cache = EvidenceCache(args.cache_path)
    llm = GroundedLLM(settings, model=model_id)

    report = enrich_pairs(
        pairs,
        registry=registry,
        llm=llm,
        cache=cache,
        prompt_template=template,
        max_total=max_total,
        dry_run=args.dry_run,
        model=model_id,
    )

    if not args.no_cache and not args.dry_run:
        cache.save()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / "substitute_evidence.json"
    csv_path = OUT_DIR / "substitute_evidence.csv"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    _write_csv(csv_path, report)

    print(
        json.dumps(
            {
                "ok": True,
                "n_pairs": report.n_pairs,
                "n_sources": report.n_sources,
                "n_cache_hits": report.n_cache_hits,
                "n_api_calls": report.n_api_calls,
                "n_failures": report.n_failures,
                "partial": report.partial,
                "duration_ms": report.duration_ms,
                "llm_model": report.llm_model,
                "report": str(json_path),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
