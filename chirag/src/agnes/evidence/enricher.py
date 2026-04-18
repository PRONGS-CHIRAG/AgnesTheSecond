"""
Phase 5 enrichment orchestration.

Selects top (source, candidate) pairs from a Phase 4 ``SubstituteCandidateReport``,
calls a grounded LLM backend once per uncached pair, and assembles a
:class:`EvidenceReport`. Pure plumbing; the only non-deterministic step is the
grounded LLM call.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from string import Template

import structlog

from agnes.models.canonical import CanonicalRegistry
from agnes.models.evidence import (
    EVIDENCE_SCHEMA_VERSION,
    EvidenceReport,
    SubstituteEvidence,
    SubstituteEvidenceLLM,
)
from agnes.models.substitutes import SubstituteCandidate, SubstituteCandidateReport
from agnes.retrieval.openai_grounded import GroundedExtractionError, GroundedLLM

logger = structlog.get_logger(__name__)

DEFAULT_CACHE_PATH = Path(".cache/phase5_evidence.json")
DEFAULT_PROMPT_PATH = Path("prompts/evidence_extraction.md")


def select_pairs(
    report: SubstituteCandidateReport,
    *,
    top_sources: int,
    per_source: int,
    source_filter: str | None = None,
) -> list[tuple[str, str]]:
    """
    Choose (source_key, candidate_key) pairs to enrich.

    Sources are ordered by the best candidate score they produced (descending),
    ties broken by source_key. For each source, the first ``per_source``
    candidates (in their existing rank order from the Phase 4 report) are taken.
    """
    if top_sources < 0 or per_source < 0:
        msg = "top_sources and per_source must be non-negative"
        raise ValueError(msg)

    by_source: dict[str, list[SubstituteCandidate]] = {}
    for cand in report.candidates:
        by_source.setdefault(cand.source_key, []).append(cand)

    if source_filter is not None:
        by_source = {source_filter: by_source.get(source_filter, [])}

    def _best(cands: list[SubstituteCandidate]) -> float:
        return cands[0].score if cands else float("-inf")

    sorted_sources = sorted(
        by_source.items(),
        key=lambda item: (-_best(item[1]), item[0]),
    )
    if top_sources:
        sorted_sources = sorted_sources[:top_sources]

    pairs: list[tuple[str, str]] = []
    for src, cands in sorted_sources:
        for cand in cands[:per_source] if per_source else cands:
            pairs.append((src, cand.candidate_key))
    return pairs


class EvidenceCache:
    """JSON-on-disk cache keyed by ``(source, candidate, model, schema_version)``."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or DEFAULT_CACHE_PATH
        self._data: dict[str, dict] = self._load()

    def _load(self) -> dict[str, dict]:
        if not self.path.is_file():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("phase5_cache_corrupt", path=str(self.path))
            return {}
        return raw if isinstance(raw, dict) else {}

    @staticmethod
    def make_key(
        source_key: str, candidate_key: str, model: str, schema_version: str
    ) -> str:
        return f"{source_key}|{candidate_key}|{model}|{schema_version}"

    def get(
        self, source_key: str, candidate_key: str, model: str
    ) -> SubstituteEvidence | None:
        key = self.make_key(source_key, candidate_key, model, EVIDENCE_SCHEMA_VERSION)
        blob = self._data.get(key)
        if blob is None:
            return None
        try:
            return SubstituteEvidence.model_validate(blob)
        except Exception:  # noqa: BLE001 — drop corrupt entry
            logger.warning("phase5_cache_entry_invalid", key=key)
            return None

    def put(self, evidence: SubstituteEvidence) -> None:
        key = self.make_key(
            evidence.source_key,
            evidence.candidate_key,
            evidence.llm_model,
            evidence.schema_version,
        )
        self._data[key] = json.loads(evidence.model_dump_json())

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, sort_keys=True), encoding="utf-8")


def load_prompt_template(path: Path | None = None) -> Template:
    """Load the Phase 5 grounded-extraction prompt template."""
    template_path = path or DEFAULT_PROMPT_PATH
    raw = template_path.read_text(encoding="utf-8")
    return Template(raw)


def _format_list(items: list[str] | None) -> str:
    if not items:
        return "unknown"
    return ", ".join(items)


def render_prompt(
    template: Template,
    *,
    source_key: str,
    source_name: str,
    source_family: str | None,
    source_roles: list[str],
    candidate_key: str,
    candidate_name: str,
    candidate_family: str | None,
    candidate_roles: list[str],
) -> str:
    """Fill the prompt template for one (source, candidate) pair."""
    return template.safe_substitute(
        source_key=source_key,
        source_name=source_name,
        source_family=source_family or "unknown",
        source_roles=_format_list(source_roles),
        candidate_key=candidate_key,
        candidate_name=candidate_name,
        candidate_family=candidate_family or "unknown",
        candidate_roles=_format_list(candidate_roles),
    )


def _resolve_material(
    registry: CanonicalRegistry,
    canonical_key: str,
) -> tuple[str, str | None, list[str]]:
    """Return ``(display_name, ingredient_family, functional_roles)`` for a key."""
    mats = [m for m in registry.materials if m.canonical_key == canonical_key]
    if not mats:
        return canonical_key.replace("-", " "), None, []
    display = mats[0].normalized_name or canonical_key.replace("-", " ")
    family = mats[0].ingredient_family
    roles = sorted({m.functional_role for m in mats if m.functional_role})
    return display, family, roles


def enrich_pairs(
    pairs: list[tuple[str, str]],
    *,
    registry: CanonicalRegistry,
    llm: GroundedLLM,
    cache: EvidenceCache,
    prompt_template: Template,
    max_total: int | None = None,
    dry_run: bool = False,
    model: str | None = None,
) -> EvidenceReport:
    """
    Enrich each ``(source, candidate)`` pair with grounded evidence.

    - Cache hits are returned verbatim and never call the backend.
    - ``max_total`` caps the number of *new* backend calls; the remaining pairs
      are skipped and ``report.partial`` is set ``True``.
    - ``dry_run=True`` makes zero backend calls and returns an empty ``items``
      list, but still reports ``n_pairs`` and intended budget.
    """
    t0 = time.perf_counter()
    resolved_model = model or llm.model

    items: list[SubstituteEvidence] = []
    n_cache_hits = 0
    n_api_calls = 0
    n_failures = 0
    partial = False
    quota_blocked = False
    sources_seen: set[str] = set()

    for idx, (source_key, candidate_key) in enumerate(pairs):
        sources_seen.add(source_key)
        logger.info(
            "phase5_pair_start",
            i=idx,
            total=len(pairs),
            source=source_key,
            candidate=candidate_key,
        )
        cached = cache.get(source_key, candidate_key, resolved_model)
        if cached is not None:
            n_cache_hits += 1
            items.append(cached)
            logger.info(
                "phase5_cache_hit",
                source=source_key,
                candidate=candidate_key,
                n_claims=len(cached.claims),
            )
            continue
        if dry_run:
            continue
        if quota_blocked:
            continue
        if max_total is not None and n_api_calls >= max_total:
            partial = True
            logger.info(
                "phase5_budget_exhausted",
                max_total=max_total,
                remaining=len(pairs) - idx,
            )
            continue

        source_name, source_family, source_roles = _resolve_material(registry, source_key)
        cand_name, cand_family, cand_roles = _resolve_material(registry, candidate_key)
        prompt = render_prompt(
            prompt_template,
            source_key=source_key,
            source_name=source_name,
            source_family=source_family,
            source_roles=source_roles,
            candidate_key=candidate_key,
            candidate_name=cand_name,
            candidate_family=cand_family,
            candidate_roles=cand_roles,
        )
        logger.info(
            "phase5_grounded_call",
            source=source_key,
            candidate=candidate_key,
            model=resolved_model,
            prompt_len=len(prompt),
        )
        try:
            parsed, citations, _raw = llm.extract(
                prompt, schema=SubstituteEvidenceLLM
            )
        except GroundedExtractionError as exc:
            n_failures += 1
            logger.warning(
                "phase5_pair_failed",
                source=source_key,
                candidate=candidate_key,
                err=str(exc)[:200],
            )
            continue
        except Exception as exc:  # noqa: BLE001 - quota or transport error; degrade gracefully
            if "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc):
                partial = True
                quota_blocked = True
                logger.warning(
                    "phase5_quota_exhausted_stop",
                    processed=idx,
                    remaining=len(pairs) - idx,
                    err=str(exc)[:200],
                )
                continue
            n_failures += 1
            logger.warning(
                "phase5_pair_failed_raw",
                source=source_key,
                candidate=candidate_key,
                err=str(exc)[:200],
            )
            continue
        n_api_calls += 1
        parsed_claims = list(parsed.claims)
        if not parsed_claims and citations:
            logger.info(
                "phase5_pair_empty_but_grounded",
                source=source_key,
                candidate=candidate_key,
                n_citations=len(citations),
            )

        evidence = SubstituteEvidence(
            source_key=source_key,
            candidate_key=candidate_key,
            claims=parsed_claims,
            n_citations=sum(len(c.citations) for c in parsed_claims),
            any_contradictions=any(c.polarity == "contradicts" for c in parsed_claims),
            retrieved_at=datetime.now(UTC),
            llm_model=resolved_model,
            schema_version=EVIDENCE_SCHEMA_VERSION,
        )
        cache.put(evidence)
        items.append(evidence)
        try:
            cache.save()
        except OSError as exc:  # pragma: no cover - best-effort flush
            logger.warning("phase5_cache_save_failed", err=str(exc))
        logger.info(
            "phase5_pair_ok",
            source=source_key,
            candidate=candidate_key,
            n_claims=len(evidence.claims),
            n_citations=evidence.n_citations,
            any_contradictions=evidence.any_contradictions,
        )

    duration_ms = int((time.perf_counter() - t0) * 1000)
    return EvidenceReport(
        schema_version=EVIDENCE_SCHEMA_VERSION,
        generated_at=datetime.now(UTC),
        llm_model=resolved_model,
        n_sources=len(sources_seen),
        n_pairs=len(pairs),
        n_cache_hits=n_cache_hits,
        n_api_calls=n_api_calls,
        n_failures=n_failures,
        duration_ms=duration_ms,
        partial=partial,
        items=items,
    )
