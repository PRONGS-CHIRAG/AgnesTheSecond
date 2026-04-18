"""End-to-end tests for Phase 5 enrichment (no network)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from string import Template
from typing import cast

from agnes.config.settings import Settings
from agnes.evidence.enricher import (
    EvidenceCache,
    enrich_pairs,
    load_prompt_template,
    render_prompt,
)
from agnes.models.canonical import (
    CanonicalMaterial,
    CanonicalRegistry,
    RegistryCoverage,
)
from agnes.models.evidence import (
    CitationRef,
    EvidenceClaim,
    SubstituteEvidenceLLM,
)
from agnes.retrieval.gemini_grounded import (
    GroundedBackend,
    GroundedLLM,
    GroundedResult,
)


def _registry() -> CanonicalRegistry:
    mats = [
        CanonicalMaterial(
            raw_product_id=1,
            sku="RM-1",
            company_id=1,
            normalized_name="calcium citrate",
            canonical_key="calcium-citrate",
            ingredient_family="vitamin_mineral",
            functional_role="active_ingredient",
            confidence=0.9,
            missing_info=[],
            parse_ok=True,
            taxonomy_version="v1",
        ),
        CanonicalMaterial(
            raw_product_id=2,
            sku="RM-2",
            company_id=2,
            normalized_name="magnesium citrate",
            canonical_key="magnesium-citrate",
            ingredient_family="vitamin_mineral",
            functional_role="active_ingredient",
            confidence=0.9,
            missing_info=[],
            parse_ok=True,
            taxonomy_version="v1",
        ),
        CanonicalMaterial(
            raw_product_id=3,
            sku="RM-3",
            company_id=1,
            normalized_name="calcium lactate",
            canonical_key="calcium-lactate",
            ingredient_family="vitamin_mineral",
            functional_role="active_ingredient",
            confidence=0.8,
            missing_info=[],
            parse_ok=True,
            taxonomy_version="v1",
        ),
    ]
    return CanonicalRegistry(
        taxonomy_version="v1",
        generated_at=datetime.now(UTC),
        unique_canonical_keys=len(mats),
        coverage=RegistryCoverage(assigned=len(mats), unassigned=0, parse_failed=0),
        materials=mats,
    )


class _ScriptedBackend:
    """Backend that returns a queued list of ``GroundedResult`` outputs."""

    def __init__(self, scripted: list[GroundedResult]) -> None:
        self._scripted = list(scripted)
        self.calls: list[tuple[str, str]] = []

    def generate(self, prompt: str, *, model: str) -> GroundedResult:
        self.calls.append((prompt, model))
        if not self._scripted:
            msg = "no scripted responses left"
            raise AssertionError(msg)
        return self._scripted.pop(0)


def _grounded_response(
    *,
    source_name: str,
    candidate_name: str,
    polarity: str = "supports",
    citation_url: str | None = "https://supplier.example.com/page",
) -> GroundedResult:
    claim = EvidenceClaim(
        key="functional_equivalence",
        value=f"{candidate_name} is widely substituted for {source_name} in mineral supplements.",
        polarity=polarity,  # type: ignore[arg-type]
        confidence=0.7,
        citations=(
            [
                CitationRef(
                    url=citation_url,
                    title="Spec",
                    domain="supplier.example.com",
                    retrieved_at=datetime(2026, 4, 18, tzinfo=UTC),
                )
            ]
            if citation_url
            else []
        ),
        grounding_strength="grounded" if citation_url else "parametric",
    )
    llm_payload = SubstituteEvidenceLLM(claims=[claim])
    json_text = llm_payload.model_dump_json()
    return GroundedResult(
        text=json_text,
        citations=list(claim.citations),
        model="gemini-2.5-flash",
    )


def _llm_with(backend: GroundedBackend) -> GroundedLLM:
    return GroundedLLM(
        Settings(gemini_api_key="test-key"),
        model="gemini-2.5-flash",
        backend=backend,
    )


def _prompt_template() -> Template:
    path = Path("prompts/evidence_extraction.md")
    if path.is_file():
        return load_prompt_template(path)
    return Template(
        "src=$source_key ($source_name/$source_family/$source_roles) "
        "cand=$candidate_key ($candidate_name/$candidate_family/$candidate_roles)"
    )


def test_render_prompt_fills_placeholders() -> None:
    template = _prompt_template()
    rendered = render_prompt(
        template,
        source_key="calcium-citrate",
        source_name="calcium citrate",
        source_family="vitamin_mineral",
        source_roles=["active_ingredient"],
        candidate_key="magnesium-citrate",
        candidate_name="magnesium citrate",
        candidate_family="vitamin_mineral",
        candidate_roles=["active_ingredient"],
    )
    assert "calcium-citrate" in rendered
    assert "magnesium-citrate" in rendered


def test_enrich_pairs_end_to_end_and_caches(tmp_path: Path) -> None:
    registry = _registry()
    backend = _ScriptedBackend(
        [
            _grounded_response(
                source_name="calcium citrate", candidate_name="magnesium citrate"
            ),
            _grounded_response(
                source_name="calcium citrate",
                candidate_name="calcium lactate",
                polarity="contradicts",
            ),
        ]
    )
    llm = _llm_with(backend)
    cache = EvidenceCache(tmp_path / "phase5.json")
    template = _prompt_template()

    pairs = [("calcium-citrate", "magnesium-citrate"), ("calcium-citrate", "calcium-lactate")]
    report = enrich_pairs(
        pairs,
        registry=registry,
        llm=llm,
        cache=cache,
        prompt_template=template,
        max_total=10,
    )
    cache.save()

    assert report.n_pairs == 2
    assert report.n_sources == 1
    assert report.n_cache_hits == 0
    assert report.n_api_calls == 2
    assert report.partial is False
    assert len(report.items) == 2
    assert report.items[0].any_contradictions is False
    assert report.items[1].any_contradictions is True
    assert cache.path.is_file()

    # Second run: no backend calls expected; all served from cache.
    backend2 = _ScriptedBackend([])
    llm2 = _llm_with(backend2)
    cache2 = EvidenceCache(cache.path)
    report2 = enrich_pairs(
        pairs,
        registry=registry,
        llm=llm2,
        cache=cache2,
        prompt_template=template,
        max_total=10,
    )
    assert report2.n_cache_hits == 2
    assert report2.n_api_calls == 0
    assert backend2.calls == []


def test_enrich_pairs_respects_max_total(tmp_path: Path) -> None:
    registry = _registry()
    backend = _ScriptedBackend(
        [
            _grounded_response(source_name="calcium citrate", candidate_name="magnesium citrate"),
        ]
    )
    llm = _llm_with(backend)
    cache = EvidenceCache(tmp_path / "phase5.json")
    template = _prompt_template()

    pairs = [("calcium-citrate", "magnesium-citrate"), ("calcium-citrate", "calcium-lactate")]
    report = enrich_pairs(
        pairs,
        registry=registry,
        llm=llm,
        cache=cache,
        prompt_template=template,
        max_total=1,
    )
    assert report.n_api_calls == 1
    assert report.partial is True
    assert len(report.items) == 1


def test_enrich_pairs_dry_run_makes_no_calls(tmp_path: Path) -> None:
    registry = _registry()
    backend = _ScriptedBackend([])
    llm = _llm_with(backend)
    cache = EvidenceCache(tmp_path / "phase5.json")
    template = _prompt_template()

    report = enrich_pairs(
        [("calcium-citrate", "magnesium-citrate")],
        registry=registry,
        llm=llm,
        cache=cache,
        prompt_template=template,
        dry_run=True,
    )
    assert report.n_api_calls == 0
    assert report.n_pairs == 1
    assert report.items == []
    assert backend.calls == []


def test_enrich_pairs_records_failure_and_continues(tmp_path: Path) -> None:
    registry = _registry()

    class _FailingBackend:
        def __init__(self) -> None:
            self.n = 0

        def generate(self, prompt: str, *, model: str) -> GroundedResult:
            self.n += 1
            return GroundedResult(text="not json!!!", citations=[], model=model)

    llm = _llm_with(cast(GroundedBackend, _FailingBackend()))
    cache = EvidenceCache(tmp_path / "phase5.json")
    template = _prompt_template()

    report = enrich_pairs(
        [("calcium-citrate", "magnesium-citrate")],
        registry=registry,
        llm=llm,
        cache=cache,
        prompt_template=template,
        max_total=5,
    )
    assert report.n_api_calls == 0
    assert report.n_failures == 1
    assert report.items == []


def test_select_pairs_and_enrichment_compose(tmp_path: Path) -> None:
    """Smoke-check: pairs selected by rank enrich in the same order."""
    registry = _registry()
    backend = _ScriptedBackend(
        [
            _grounded_response(source_name="calcium citrate", candidate_name="magnesium citrate"),
        ]
    )
    llm = _llm_with(backend)
    cache = EvidenceCache(tmp_path / "phase5.json")
    template = _prompt_template()

    pairs = [("calcium-citrate", "magnesium-citrate")]
    report = enrich_pairs(
        pairs,
        registry=registry,
        llm=llm,
        cache=cache,
        prompt_template=template,
        max_total=10,
    )
    assert report.items[0].source_key == "calcium-citrate"
    assert report.items[0].candidate_key == "magnesium-citrate"
    assert report.items[0].gemini_model == "gemini-2.5-flash"
