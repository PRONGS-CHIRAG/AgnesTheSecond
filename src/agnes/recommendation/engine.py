"""
Phase 7 orchestrator.

Runs after :mod:`agnes.recommendation.builder` has produced deterministic
rows + rollups. Optionally polishes the top-N opportunities via
:class:`SummaryLLM`, propagating the polished summary back into both the
rollup row and the per-tuple rows it covers. Polish results are cached to
``.cache/phase7_recommendations.json`` keyed on
``(source_key, candidate_key, model, RECOMMENDATION_SCHEMA_VERSION)``.
"""

from __future__ import annotations

import json
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from string import Template

import structlog

from agnes.models.recommendation import (
    RECOMMENDATION_SCHEMA_VERSION,
    ConsolidationOpportunity,
    RecommendationReport,
    SourcingRecommendation,
)
from agnes.recommendation.llm_polish import (
    RecommendationLLMError,
    SummaryLLM,
    SummaryLLMResponse,
    render_prompt,
)

logger = structlog.get_logger(__name__)

DEFAULT_CACHE_PATH = Path(".cache/phase7_recommendations.json")


class RecommendationCache:
    """JSON-on-disk cache of LLM polish responses, keyed by candidate + model."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or DEFAULT_CACHE_PATH
        self._data: dict[str, dict] = self._load()

    def _load(self) -> dict[str, dict]:
        if not self.path.is_file():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("phase7_cache_corrupt", path=str(self.path))
            return {}
        return raw if isinstance(raw, dict) else {}

    @staticmethod
    def make_key(
        opportunity: ConsolidationOpportunity,
        *,
        model: str,
        schema_version: str = RECOMMENDATION_SCHEMA_VERSION,
    ) -> str:
        return (
            f"{opportunity.source_key}|{opportunity.best_candidate_key}|"
            f"{model}|{schema_version}"
        )

    def get(
        self,
        opportunity: ConsolidationOpportunity,
        *,
        model: str,
    ) -> SummaryLLMResponse | None:
        key = self.make_key(opportunity, model=model)
        blob = self._data.get(key)
        if blob is None:
            return None
        try:
            return SummaryLLMResponse.model_validate(blob)
        except Exception:  # noqa: BLE001 — drop corrupt entry
            logger.warning("phase7_cache_entry_invalid", key=key)
            return None

    def put(
        self,
        opportunity: ConsolidationOpportunity,
        response: SummaryLLMResponse,
        *,
        model: str,
    ) -> None:
        key = self.make_key(opportunity, model=model)
        self._data[key] = json.loads(response.model_dump_json())

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, sort_keys=True), encoding="utf-8")


def _apply_polish_to_rows(
    rows: list[SourcingRecommendation],
    *,
    top_row_keys: list[str],
    polished: SummaryLLMResponse,
    now: datetime,
    model: str,
) -> list[SourcingRecommendation]:
    key_set = set(top_row_keys)
    out: list[SourcingRecommendation] = []
    for row in rows:
        if row.row_key() in key_set:
            merged_notes = list(row.risk_notes)
            for note in polished.risk_notes:
                if note not in merged_notes:
                    merged_notes.append(note)
            out.append(
                row.model_copy(
                    update={
                        "tradeoff_summary": polished.tradeoff_summary,
                        "risk_notes": merged_notes,
                        "decision_path": "llm",
                        "llm_model": model,
                        "generated_at": now,
                    }
                )
            )
        else:
            out.append(row)
    return out


def generate_report(
    rows: list[SourcingRecommendation],
    opportunities: list[ConsolidationOpportunity],
    *,
    llm: SummaryLLM | None,
    cache: RecommendationCache,
    template: Template | None,
    weights: dict[str, float],
    thresholds: dict[str, float],
    top_n_polish: int = 5,
    max_llm_calls: int = 10,
    dry_run: bool = False,
) -> RecommendationReport:
    """
    Build the :class:`RecommendationReport` and, budget permitting, polish the
    top-N opportunities' ``tradeoff_summary`` via :class:`SummaryLLM`.

    Any failure path preserves the deterministic summary produced by
    :func:`agnes.recommendation.builder.rollup_opportunities`.
    """
    t0 = time.perf_counter()
    llm_model = llm.model if llm is not None else None

    n_cache_hits = 0
    n_api_calls = 0
    n_failures = 0
    partial = False

    polished_opps: list[ConsolidationOpportunity] = []
    rows_working = list(rows)

    sorted_opps = sorted(
        opportunities, key=lambda o: (-o.aggregate_final_score, o.source_key)
    )
    to_polish = sorted_opps[:top_n_polish]
    passthrough = sorted_opps[top_n_polish:]

    for opportunity in to_polish:
        if (
            llm is None
            or template is None
            or dry_run
            or llm_model is None
        ):
            polished_opps.append(opportunity)
            continue

        cached = cache.get(opportunity, model=llm_model)
        now = datetime.now(UTC)
        if cached is not None:
            n_cache_hits += 1
            logger.info(
                "phase7_cache_hit",
                source=opportunity.source_key,
                candidate=opportunity.best_candidate_key,
                model=llm_model,
            )
            updated = opportunity.model_copy(
                update={
                    "tradeoff_summary": cached.tradeoff_summary,
                    "risk_notes": _merge_notes(opportunity.risk_notes, cached.risk_notes),
                    "decision_path": "llm",
                    "llm_model": llm_model,
                    "generated_at": now,
                }
            )
            polished_opps.append(updated)
            rows_working = _apply_polish_to_rows(
                rows_working,
                top_row_keys=opportunity.top_row_keys,
                polished=cached,
                now=now,
                model=llm_model,
            )
            continue

        if n_api_calls >= max_llm_calls:
            partial = True
            logger.info(
                "phase7_budget_exhausted",
                max_llm_calls=max_llm_calls,
                source=opportunity.source_key,
            )
            polished_opps.append(opportunity)
            continue

        top_rows = [
            r for r in rows_working if r.row_key() in set(opportunity.top_row_keys)
        ]
        prompt = render_prompt(template, opportunity=opportunity, top_rows=top_rows)
        logger.info(
            "phase7_llm_call",
            source=opportunity.source_key,
            candidate=opportunity.best_candidate_key,
            model=llm_model,
            prompt_len=len(prompt),
        )
        try:
            parsed, _raw = llm.polish(prompt)
        except RecommendationLLMError as exc:
            n_failures += 1
            logger.warning(
                "phase7_llm_failed",
                source=opportunity.source_key,
                candidate=opportunity.best_candidate_key,
                err=str(exc)[:200],
            )
            polished_opps.append(opportunity)
            continue

        n_api_calls += 1
        cache.put(opportunity, parsed, model=llm_model)
        updated = opportunity.model_copy(
            update={
                "tradeoff_summary": parsed.tradeoff_summary,
                "risk_notes": _merge_notes(opportunity.risk_notes, parsed.risk_notes),
                "decision_path": "llm",
                "llm_model": llm_model,
                "generated_at": now,
            }
        )
        polished_opps.append(updated)
        rows_working = _apply_polish_to_rows(
            rows_working,
            top_row_keys=opportunity.top_row_keys,
            polished=parsed,
            now=now,
            model=llm_model,
        )
        logger.info(
            "phase7_llm_ok",
            source=opportunity.source_key,
            candidate=opportunity.best_candidate_key,
            model=llm_model,
        )

    polished_opps.extend(passthrough)
    polished_opps.sort(key=lambda o: (-o.aggregate_final_score, o.source_key))

    counts = Counter(r.recommendation_grade for r in rows_working)
    duration_ms = int((time.perf_counter() - t0) * 1000)
    return RecommendationReport(
        schema_version=RECOMMENDATION_SCHEMA_VERSION,
        generated_at=datetime.now(UTC),
        llm_model=llm_model,
        weights=weights,
        thresholds=thresholds,
        n_tuples=len(rows_working),
        n_opportunities=len(polished_opps),
        n_cache_hits=n_cache_hits,
        n_api_calls=n_api_calls,
        n_failures=n_failures,
        counts_by_grade=dict(counts),
        duration_ms=duration_ms,
        partial=partial,
        items=rows_working,
        opportunities=polished_opps,
    )


def _merge_notes(existing: list[str], new: list[str]) -> list[str]:
    out = list(existing)
    for note in new:
        if note not in out:
            out.append(note)
    return out
