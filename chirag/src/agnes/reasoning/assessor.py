"""
Phase 6 orchestration: aggregate Phase 5 evidence into typed substitute
assessments per (company, product, source, candidate) tuple.

Pipeline per tuple:

1. Look up the pair's :class:`SubstituteEvidence` in the Phase 5 report.
2. Run deterministic rules (:mod:`agnes.reasoning.rules`) → initial verdict.
3. If confident, emit ``decision_path="rules"``.
4. If borderline and we still have LLM budget, call the structured fallback.
5. On LLM failure, fall back to the rules verdict and bump ``n_failures``.

Everything is cached to ``.cache/phase6_assessments.json`` keyed on the tuple
identity **plus** the schema version and model id, so changing weights /
thresholds / model id cleanly invalidates old entries.
"""

from __future__ import annotations

import json
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from string import Template

import structlog

from agnes.models.assessment import (
    ASSESSMENT_SCHEMA_VERSION,
    AssessmentContext,
    AssessmentReport,
    SubstituteAssessment,
    SubstituteAssessmentLLM,
)
from agnes.models.evidence import SubstituteEvidence
from agnes.reasoning.llm_fallback import (
    AssessmentLLMError,
    StructuredLLM,
    claims_to_json,
    render_prompt,
)
from agnes.reasoning.rules import (
    RulesConfig,
    aggregate_claims,
    classify,
    deterministic_rationale,
    score_acceptability,
)

logger = structlog.get_logger(__name__)

DEFAULT_CACHE_PATH = Path(".cache/phase6_assessments.json")


def _empty_evidence(source_key: str, candidate_key: str) -> SubstituteEvidence:
    """Stand-in evidence for tuples with no Phase 5 pair."""
    return SubstituteEvidence(
        source_key=source_key,
        candidate_key=candidate_key,
        claims=[],
        n_citations=0,
        any_contradictions=False,
        retrieved_at=datetime.now(UTC),
        llm_model="none",
    )


class AssessmentCache:
    """JSON-on-disk cache keyed by tuple + schema + model."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or DEFAULT_CACHE_PATH
        self._data: dict[str, dict] = self._load()

    def _load(self) -> dict[str, dict]:
        if not self.path.is_file():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("phase6_cache_corrupt", path=str(self.path))
            return {}
        return raw if isinstance(raw, dict) else {}

    @staticmethod
    def make_key(
        ctx: AssessmentContext,
        *,
        model_or_rules: str,
        schema_version: str,
    ) -> str:
        return (
            f"{ctx.company_id}|{ctx.finished_product_id}|"
            f"{ctx.source_key}|{ctx.candidate_key}|"
            f"{model_or_rules}|{schema_version}"
        )

    def get(
        self,
        ctx: AssessmentContext,
        *,
        model_or_rules: str,
    ) -> SubstituteAssessment | None:
        key = self.make_key(
            ctx,
            model_or_rules=model_or_rules,
            schema_version=ASSESSMENT_SCHEMA_VERSION,
        )
        blob = self._data.get(key)
        if blob is None:
            return None
        try:
            return SubstituteAssessment.model_validate(blob)
        except Exception:  # noqa: BLE001 — drop corrupt entry
            logger.warning("phase6_cache_entry_invalid", key=key)
            return None

    def put(
        self,
        ctx: AssessmentContext,
        assessment: SubstituteAssessment,
        *,
        model_or_rules: str,
    ) -> None:
        key = self.make_key(
            ctx,
            model_or_rules=model_or_rules,
            schema_version=ASSESSMENT_SCHEMA_VERSION,
        )
        self._data[key] = json.loads(assessment.model_dump_json())

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, sort_keys=True), encoding="utf-8")


def _cache_discriminator(decision_path: str, llm_model: str | None) -> str:
    if decision_path == "llm" and llm_model:
        return llm_model
    return "rules"


def _build_rules_assessment(
    ctx: AssessmentContext,
    evidence: SubstituteEvidence,
    cls: str,
    acceptability: float,
    agg,
    *,
    now: datetime,
) -> SubstituteAssessment:
    return SubstituteAssessment(
        company_id=ctx.company_id,
        company_name=ctx.company_name,
        finished_product_id=ctx.finished_product_id,
        finished_product_sku=ctx.finished_product_sku,
        source_key=ctx.source_key,
        candidate_key=ctx.candidate_key,
        source_display_name=ctx.source_display_name,
        candidate_display_name=ctx.candidate_display_name,
        recommendation_class=cls,  # type: ignore[arg-type]
        acceptability=acceptability,
        missing_information=list(agg.missing_information),
        contradictions=list(agg.contradictions),
        caveats=[],
        rationale=deterministic_rationale(cls, acceptability, agg),  # type: ignore[arg-type]
        decision_path="rules",
        citations_used=list(agg.citations),
        substitute_score=ctx.substitute_score,
        generated_at=now,
        llm_model=None,
    )


def _merge_llm(
    rules_assessment: SubstituteAssessment,
    llm_out: SubstituteAssessmentLLM,
    *,
    llm_model: str,
    now: datetime,
) -> SubstituteAssessment:
    """Merge LLM verdict on top of the rules assessment (preserves rules telemetry)."""
    return rules_assessment.model_copy(
        update={
            "recommendation_class": llm_out.recommendation_class,
            "rationale": llm_out.rationale.strip() or rules_assessment.rationale,
            "caveats": list(llm_out.caveats),
            "missing_information": (
                list(llm_out.missing_information)
                or list(rules_assessment.missing_information)
            ),
            "decision_path": "llm",
            "llm_model": llm_model,
            "generated_at": now,
        }
    )


def assess_contexts(
    contexts: list[AssessmentContext],
    evidence_by_pair: dict[tuple[str, str], SubstituteEvidence],
    *,
    rules_cfg: RulesConfig,
    llm: StructuredLLM | None,
    cache: AssessmentCache,
    template: Template | None,
    max_llm_calls: int = 25,
    dry_run: bool = False,
) -> AssessmentReport:
    """
    Run the rules pipeline (plus LLM fallback where budgeted) over ``contexts``.

    Parameters
    ----------
    contexts:
        Output of :func:`agnes.reasoning.context.expand_context`.
    evidence_by_pair:
        Fast lookup from ``(source_key, candidate_key)`` to Phase 5 evidence.
        Pairs with no entry are scored as ``insufficient_evidence``.
    rules_cfg:
        Weights + thresholds.
    llm:
        Structured LLM client. May be ``None`` when budget is zero or ``dry_run``.
    cache:
        On-disk cache of prior assessments.
    template:
        Phase 6 prompt template (required unless ``llm`` is ``None``).
    max_llm_calls:
        Hard cap on new LLM calls this run. Cache hits do not count.
    dry_run:
        If True, never call the backend; only rules + cache lookups run.
    """
    t0 = time.perf_counter()
    llm_model = llm.model if llm is not None else None

    items: list[SubstituteAssessment] = []
    n_rules_decisions = 0
    n_llm_decisions = 0
    n_cache_hits = 0
    n_api_calls = 0
    n_failures = 0
    n_without_evidence = 0
    partial = False

    for idx, ctx in enumerate(contexts):
        logger.info(
            "phase6_tuple_start",
            i=idx,
            total=len(contexts),
            company_id=ctx.company_id,
            product_id=ctx.finished_product_id,
            source=ctx.source_key,
            candidate=ctx.candidate_key,
        )

        evidence = evidence_by_pair.get((ctx.source_key, ctx.candidate_key))
        if evidence is None:
            n_without_evidence += 1
            evidence = _empty_evidence(ctx.source_key, ctx.candidate_key)

        agg = aggregate_claims(evidence)
        acceptability = score_acceptability(agg, rules_cfg)
        cls, borderline = classify(acceptability, agg, rules_cfg)

        now = datetime.now(UTC)
        rules_assessment = _build_rules_assessment(
            ctx, evidence, cls, acceptability, agg, now=now
        )

        want_llm = (
            borderline
            and not dry_run
            and llm is not None
            and template is not None
            and n_api_calls < max_llm_calls
        )

        discriminator = _cache_discriminator(
            "llm" if want_llm else "rules", llm_model
        )
        cached = cache.get(ctx, model_or_rules=discriminator)
        if cached is not None:
            n_cache_hits += 1
            if cached.decision_path == "llm":
                n_llm_decisions += 1
            else:
                n_rules_decisions += 1
            items.append(cached)
            logger.info(
                "phase6_cache_hit",
                company_id=ctx.company_id,
                product_id=ctx.finished_product_id,
                source=ctx.source_key,
                candidate=ctx.candidate_key,
                decision_path=cached.decision_path,
            )
            continue

        if not want_llm:
            if borderline and llm is not None and n_api_calls >= max_llm_calls:
                partial = True
                logger.info(
                    "phase6_budget_exhausted",
                    max_llm_calls=max_llm_calls,
                    company_id=ctx.company_id,
                    product_id=ctx.finished_product_id,
                )
            logger.info(
                "phase6_rules_decision",
                company_id=ctx.company_id,
                product_id=ctx.finished_product_id,
                source=ctx.source_key,
                candidate=ctx.candidate_key,
                recommendation_class=cls,
                acceptability=round(acceptability, 4),
                borderline=borderline,
            )
            n_rules_decisions += 1
            items.append(rules_assessment)
            cache.put(ctx, rules_assessment, model_or_rules="rules")
            continue

        claims_json = claims_to_json(evidence)
        rules_summary = deterministic_rationale(cls, acceptability, agg)
        prompt = render_prompt(
            template,  # type: ignore[arg-type]
            company=ctx.company_name or f"company-{ctx.company_id}",
            product=ctx.finished_product_sku
            or f"product-{ctx.finished_product_id}",
            source_key=ctx.source_key,
            source_name=ctx.source_display_name,
            candidate_key=ctx.candidate_key,
            candidate_name=ctx.candidate_display_name,
            claims_json=claims_json,
            rules_summary=rules_summary,
        )
        logger.info(
            "phase6_llm_call",
            company_id=ctx.company_id,
            product_id=ctx.finished_product_id,
            source=ctx.source_key,
            candidate=ctx.candidate_key,
            model=llm_model,
            prompt_len=len(prompt),
        )
        try:
            parsed, _raw = llm.assess(prompt)  # type: ignore[union-attr]
        except AssessmentLLMError as exc:
            n_failures += 1
            n_rules_decisions += 1
            logger.warning(
                "phase6_llm_failed",
                company_id=ctx.company_id,
                product_id=ctx.finished_product_id,
                source=ctx.source_key,
                candidate=ctx.candidate_key,
                err=str(exc)[:200],
            )
            items.append(rules_assessment)
            cache.put(ctx, rules_assessment, model_or_rules="rules")
            continue

        n_api_calls += 1
        assert llm_model is not None
        merged = _merge_llm(rules_assessment, parsed, llm_model=llm_model, now=now)
        n_llm_decisions += 1
        items.append(merged)
        cache.put(ctx, merged, model_or_rules=llm_model)
        logger.info(
            "phase6_llm_ok",
            company_id=ctx.company_id,
            product_id=ctx.finished_product_id,
            source=ctx.source_key,
            candidate=ctx.candidate_key,
            recommendation_class=merged.recommendation_class,
        )

    counts = Counter(a.recommendation_class for a in items)
    duration_ms = int((time.perf_counter() - t0) * 1000)
    return AssessmentReport(
        schema_version=ASSESSMENT_SCHEMA_VERSION,
        generated_at=datetime.now(UTC),
        llm_model=llm_model,
        weights=dict(rules_cfg.claim_weights),
        thresholds={
            "accept": rules_cfg.accept_threshold,
            "reject": rules_cfg.reject_threshold,
            "min_grounded_claims": float(rules_cfg.min_grounded_claims),
        },
        n_tuples=len(contexts),
        n_rules_decisions=n_rules_decisions,
        n_llm_decisions=n_llm_decisions,
        n_cache_hits=n_cache_hits,
        n_api_calls=n_api_calls,
        n_failures=n_failures,
        n_without_evidence=n_without_evidence,
        counts_by_class=dict(counts),
        duration_ms=duration_ms,
        partial=partial,
        items=items,
    )
