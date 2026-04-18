#!/usr/bin/env python3
"""Phase 6: turn Phase 5 evidence into typed substitute assessments."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from agnes.config.settings import Settings
from agnes.data.db_loader import get_engine
from agnes.models.canonical import CanonicalRegistry
from agnes.models.evidence import EvidenceReport
from agnes.models.substitutes import SubstituteCandidateReport
from agnes.reasoning.assessor import (
    DEFAULT_CACHE_PATH,
    AssessmentCache,
    assess_contexts,
)
from agnes.reasoning.context import expand_context
from agnes.reasoning.llm_fallback import (
    DEFAULT_PROMPT_PATH,
    StructuredLLM,
    load_prompt_template,
)
from agnes.reasoning.rules import DEFAULT_CLAIM_WEIGHTS, RulesConfig
from agnes.utils.logging import configure_logging

OUT_DIR = Path("outputs/reports")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run Phase 6 context and compliance reasoning.",
    )
    p.add_argument(
        "--evidence",
        type=Path,
        default=Path("outputs/reports/substitute_evidence.json"),
        help="Phase 5 EvidenceReport input.",
    )
    p.add_argument(
        "--candidates",
        type=Path,
        default=Path("outputs/reports/substitute_candidates.json"),
        help="Phase 4 SubstituteCandidateReport (for passthrough scores).",
    )
    p.add_argument(
        "--registry",
        type=Path,
        default=Path("outputs/reports/canonical_registry.json"),
        help="Phase 2 CanonicalRegistry for material display + raw-id lookup.",
    )
    p.add_argument(
        "--max-llm-calls",
        type=int,
        default=None,
        help="Cap on new LLM fallback calls (default: settings.phase6_max_llm_calls).",
    )
    p.add_argument(
        "--model",
        type=str,
        default=None,
        help="Structured-LLM model id (default: settings.phase6_llm_model).",
    )
    p.add_argument(
        "--prompt",
        type=Path,
        default=DEFAULT_PROMPT_PATH,
        help="Path to the Phase 6 assessment prompt template.",
    )
    p.add_argument(
        "--cache-path",
        type=Path,
        default=DEFAULT_CACHE_PATH,
        help="Path to the assessment disk cache.",
    )
    p.add_argument(
        "--no-cache",
        action="store_true",
        help="Do not persist the assessment cache back to disk.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Run rules + cache lookups only; skip LLM fallback entirely.",
    )
    p.add_argument(
        "--source",
        type=str,
        default=None,
        help="Restrict to one source canonical_key.",
    )
    p.add_argument(
        "--company",
        type=int,
        default=None,
        help="Restrict to one CompanyId.",
    )
    return p.parse_args()


def _parse_weights(raw: str) -> dict[str, float]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return dict(DEFAULT_CLAIM_WEIGHTS)
    if not isinstance(parsed, dict):
        return dict(DEFAULT_CLAIM_WEIGHTS)
    merged = dict(DEFAULT_CLAIM_WEIGHTS)
    for k, v in parsed.items():
        try:
            merged[str(k)] = float(v)
        except (TypeError, ValueError):
            continue
    return merged


def _write_csv(path: Path, report) -> None:
    rows = []
    for item in report.items:
        rows.append(
            {
                "company_id": item.company_id,
                "company_name": item.company_name or "",
                "finished_product_id": item.finished_product_id,
                "finished_product_sku": item.finished_product_sku or "",
                "source_key": item.source_key,
                "candidate_key": item.candidate_key,
                "source_display_name": item.source_display_name,
                "candidate_display_name": item.candidate_display_name,
                "recommendation_class": item.recommendation_class,
                "acceptability": round(item.acceptability, 4),
                "decision_path": item.decision_path,
                "missing_information": json.dumps(item.missing_information),
                "contradictions": json.dumps(item.contradictions),
                "caveats": json.dumps(item.caveats),
                "rationale": item.rationale,
                "citations": json.dumps([c.url for c in item.citations_used]),
                "substitute_score": (
                    round(item.substitute_score, 4)
                    if item.substitute_score is not None
                    else ""
                ),
                "llm_model": item.llm_model or "",
                "generated_at": item.generated_at.isoformat(),
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

    for label, path in (
        ("evidence_missing", args.evidence),
        ("registry_missing", args.registry),
    ):
        if not path.is_file():
            print(json.dumps({"error": label, "path": str(path)}), file=sys.stderr)
            return 1

    evidence_report = EvidenceReport.model_validate_json(
        args.evidence.read_text(encoding="utf-8")
    )
    registry = CanonicalRegistry.model_validate_json(
        args.registry.read_text(encoding="utf-8")
    )
    candidates_report: SubstituteCandidateReport | None = None
    if args.candidates.is_file():
        candidates_report = SubstituteCandidateReport.model_validate_json(
            args.candidates.read_text(encoding="utf-8")
        )

    engine = get_engine(settings)
    contexts = expand_context(
        registry,
        engine,
        evidence_report,
        candidates_report=candidates_report,
    )

    if args.source:
        contexts = [c for c in contexts if c.source_key == args.source]
    if args.company is not None:
        contexts = [c for c in contexts if c.company_id == args.company]

    if not contexts:
        print(
            json.dumps(
                {
                    "ok": False,
                    "reason": "no_contexts",
                    "hint": "check registry / DB / Phase 5 evidence coverage",
                }
            )
        )
        return 0

    weights = _parse_weights(settings.phase6_claim_weights)
    rules_cfg = RulesConfig(
        claim_weights=weights,
        accept_threshold=settings.phase6_accept_threshold,
        reject_threshold=settings.phase6_reject_threshold,
        min_grounded_claims=settings.phase6_min_grounded_claims,
    )
    max_llm_calls = (
        args.max_llm_calls
        if args.max_llm_calls is not None
        else settings.phase6_max_llm_calls
    )
    model_id = args.model or settings.phase6_llm_model

    llm: StructuredLLM | None = None
    template = None
    if not args.dry_run and max_llm_calls > 0:
        template = load_prompt_template(args.prompt)
        llm = StructuredLLM(settings, model=model_id)

    cache = AssessmentCache(args.cache_path)
    evidence_by_pair = {
        (ev.source_key, ev.candidate_key): ev for ev in evidence_report.items
    }
    report = assess_contexts(
        contexts,
        evidence_by_pair,
        rules_cfg=rules_cfg,
        llm=llm,
        cache=cache,
        template=template,
        max_llm_calls=max_llm_calls,
        dry_run=args.dry_run,
    )

    if not args.no_cache and not args.dry_run:
        cache.save()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / "substitute_assessments.json"
    csv_path = OUT_DIR / "substitute_assessments.csv"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    _write_csv(csv_path, report)

    print(
        json.dumps(
            {
                "ok": True,
                "n_tuples": report.n_tuples,
                "n_rules_decisions": report.n_rules_decisions,
                "n_llm_decisions": report.n_llm_decisions,
                "n_cache_hits": report.n_cache_hits,
                "n_api_calls": report.n_api_calls,
                "n_failures": report.n_failures,
                "n_without_evidence": report.n_without_evidence,
                "counts_by_class": report.counts_by_class,
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
