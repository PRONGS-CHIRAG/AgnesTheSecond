"""Phase 6 assessor end-to-end with a stubbed structured LLM."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from string import Template
from typing import cast

from agnes.config.settings import Settings
from agnes.models.assessment import AssessmentContext
from agnes.models.evidence import (
    CitationRef,
    EvidenceClaim,
    SubstituteEvidence,
)
from agnes.reasoning.assessor import (
    AssessmentCache,
    assess_contexts,
)
from agnes.reasoning.llm_fallback import (
    StructuredBackend,
    StructuredLLM,
    StructuredResult,
)
from agnes.reasoning.rules import DEFAULT_CLAIM_WEIGHTS, RulesConfig


def _cite() -> CitationRef:
    return CitationRef(
        url="https://example.com/doc",
        title="Doc",
        domain="example.com",
        retrieved_at=datetime(2026, 4, 18, tzinfo=UTC),
    )


def _claim(
    key: str,
    *,
    polarity: str = "supports",
    confidence: float = 0.8,
    grounded: bool = True,
) -> EvidenceClaim:
    return EvidenceClaim(
        key=key,  # type: ignore[arg-type]
        value="...",
        polarity=polarity,  # type: ignore[arg-type]
        confidence=confidence,
        citations=[_cite()] if grounded else [],
        grounding_strength="grounded" if grounded else "parametric",
    )


def _evidence(source: str, candidate: str, *claims: EvidenceClaim) -> SubstituteEvidence:
    return SubstituteEvidence(
        source_key=source,
        candidate_key=candidate,
        claims=list(claims),
        n_citations=sum(len(c.citations) for c in claims),
        any_contradictions=any(c.polarity == "contradicts" for c in claims),
        retrieved_at=datetime.now(UTC),
        llm_model="gpt-4o-mini",
    )


def _ctx(
    source: str,
    candidate: str,
    company_id: int = 1,
    product_id: int = 10,
) -> AssessmentContext:
    return AssessmentContext(
        company_id=company_id,
        company_name="Acme",
        finished_product_id=product_id,
        finished_product_sku=f"ACME-{product_id}",
        source_key=source,
        candidate_key=candidate,
        source_display_name=source.replace("-", " "),
        candidate_display_name=candidate.replace("-", " "),
        substitute_score=0.80,
    )


class _ScriptedBackend:
    def __init__(self, texts: list[str]) -> None:
        self._texts = list(texts)
        self.calls = 0

    def generate(self, prompt: str, *, model: str) -> StructuredResult:
        self.calls += 1
        if not self._texts:
            raise AssertionError("no more scripted responses")
        return StructuredResult(text=self._texts.pop(0), model=model)


def _llm_with(backend: StructuredBackend) -> StructuredLLM:
    return StructuredLLM(
        Settings(openai_api_key="test-key"),
        model="gpt-4o-mini",
        backend=backend,
    )


def _template() -> Template:
    return Template(
        "company=$company product=$product src=$source_key cand=$candidate_key "
        "rules=$rules_summary claims=$claims_json"
    )


def _rules_cfg() -> RulesConfig:
    return RulesConfig(
        claim_weights=dict(DEFAULT_CLAIM_WEIGHTS),
        accept_threshold=0.75,
        reject_threshold=0.35,
        min_grounded_claims=2,
    )


def _llm_json(cls: str = "recommend_with_caveats") -> str:
    return json.dumps(
        {
            "recommendation_class": cls,
            "rationale": "llm-rationale",
            "caveats": ["requires review"],
            "missing_information": ["certification"],
        }
    )


def test_confident_rules_path_never_calls_llm(tmp_path: Path) -> None:
    ctx = _ctx("calcium-citrate", "magnesium-citrate")
    evidence = _evidence(
        "calcium-citrate",
        "magnesium-citrate",
        _claim("functional_equivalence", confidence=1.0),
        _claim("regulatory", confidence=1.0),
        _claim("certification", confidence=1.0),
        _claim("quality_sensory", confidence=1.0),
    )
    backend = _ScriptedBackend([])
    llm = _llm_with(cast(StructuredBackend, backend))
    cache = AssessmentCache(tmp_path / "phase6.json")

    report = assess_contexts(
        [ctx],
        {(ctx.source_key, ctx.candidate_key): evidence},
        rules_cfg=_rules_cfg(),
        llm=llm,
        cache=cache,
        template=_template(),
        max_llm_calls=5,
    )

    assert report.n_tuples == 1
    assert report.n_rules_decisions == 1
    assert report.n_llm_decisions == 0
    assert report.n_api_calls == 0
    assert report.items[0].decision_path == "rules"
    assert report.items[0].recommendation_class == "recommend"
    assert backend.calls == 0


def test_borderline_invokes_llm_and_merges(tmp_path: Path) -> None:
    ctx = _ctx("calcium-citrate", "magnesium-citrate")
    evidence = _evidence(
        "calcium-citrate",
        "magnesium-citrate",
        _claim("functional_equivalence", confidence=0.7),
        _claim("price_availability", confidence=0.6),
    )
    backend = _ScriptedBackend([_llm_json("recommend_with_caveats")])
    llm = _llm_with(cast(StructuredBackend, backend))
    cache = AssessmentCache(tmp_path / "phase6.json")

    report = assess_contexts(
        [ctx],
        {(ctx.source_key, ctx.candidate_key): evidence},
        rules_cfg=_rules_cfg(),
        llm=llm,
        cache=cache,
        template=_template(),
        max_llm_calls=5,
    )

    assert report.n_api_calls == 1
    assert report.n_llm_decisions == 1
    assert report.n_rules_decisions == 0
    item = report.items[0]
    assert item.decision_path == "llm"
    assert item.rationale == "llm-rationale"
    assert item.caveats == ["requires review"]
    assert item.missing_information == ["certification"]
    assert item.llm_model == "gpt-4o-mini"


def test_cache_hit_on_rerun(tmp_path: Path) -> None:
    ctx = _ctx("calcium-citrate", "magnesium-citrate")
    evidence = _evidence(
        "calcium-citrate",
        "magnesium-citrate",
        _claim("functional_equivalence", confidence=0.7),
        _claim("price_availability", confidence=0.6),
    )
    cache_path = tmp_path / "phase6.json"

    backend1 = _ScriptedBackend([_llm_json()])
    llm1 = _llm_with(cast(StructuredBackend, backend1))
    cache1 = AssessmentCache(cache_path)
    report1 = assess_contexts(
        [ctx],
        {(ctx.source_key, ctx.candidate_key): evidence},
        rules_cfg=_rules_cfg(),
        llm=llm1,
        cache=cache1,
        template=_template(),
        max_llm_calls=5,
    )
    cache1.save()
    assert report1.n_api_calls == 1

    backend2 = _ScriptedBackend([])
    llm2 = _llm_with(cast(StructuredBackend, backend2))
    cache2 = AssessmentCache(cache_path)
    report2 = assess_contexts(
        [ctx],
        {(ctx.source_key, ctx.candidate_key): evidence},
        rules_cfg=_rules_cfg(),
        llm=llm2,
        cache=cache2,
        template=_template(),
        max_llm_calls=5,
    )
    assert report2.n_api_calls == 0
    assert report2.n_cache_hits == 1
    assert backend2.calls == 0


def test_budget_exhaustion_marks_partial(tmp_path: Path) -> None:
    evidence_common = [
        _claim("functional_equivalence", confidence=0.7),
        _claim("price_availability", confidence=0.6),
    ]
    ctxs = [
        _ctx("calcium-citrate", "magnesium-citrate", product_id=10),
        _ctx("calcium-citrate", "calcium-lactate", product_id=11),
    ]
    evidence = {
        (c.source_key, c.candidate_key): _evidence(
            c.source_key, c.candidate_key, *evidence_common
        )
        for c in ctxs
    }

    backend = _ScriptedBackend([_llm_json()])
    llm = _llm_with(cast(StructuredBackend, backend))
    cache = AssessmentCache(tmp_path / "phase6.json")

    report = assess_contexts(
        ctxs,
        evidence,
        rules_cfg=_rules_cfg(),
        llm=llm,
        cache=cache,
        template=_template(),
        max_llm_calls=1,
    )
    assert report.n_api_calls == 1
    assert report.n_rules_decisions == 1
    assert report.n_llm_decisions == 1
    assert report.partial is True


def test_llm_failure_falls_back_to_rules(tmp_path: Path) -> None:
    ctx = _ctx("calcium-citrate", "magnesium-citrate")
    evidence = _evidence(
        "calcium-citrate",
        "magnesium-citrate",
        _claim("functional_equivalence", confidence=0.7),
        _claim("price_availability", confidence=0.6),
    )
    backend = _ScriptedBackend(["garbage", "still garbage"])
    llm = _llm_with(cast(StructuredBackend, backend))
    cache = AssessmentCache(tmp_path / "phase6.json")

    report = assess_contexts(
        [ctx],
        {(ctx.source_key, ctx.candidate_key): evidence},
        rules_cfg=_rules_cfg(),
        llm=llm,
        cache=cache,
        template=_template(),
        max_llm_calls=5,
    )
    assert report.n_failures == 1
    assert report.n_rules_decisions == 1
    assert report.n_llm_decisions == 0
    assert report.items[0].decision_path == "rules"


def test_dry_run_skips_llm_and_cache_writes(tmp_path: Path) -> None:
    ctx = _ctx("calcium-citrate", "magnesium-citrate")
    evidence = _evidence(
        "calcium-citrate",
        "magnesium-citrate",
        _claim("functional_equivalence", confidence=0.7),
        _claim("price_availability", confidence=0.6),
    )
    backend = _ScriptedBackend([])
    llm = _llm_with(cast(StructuredBackend, backend))
    cache = AssessmentCache(tmp_path / "phase6.json")

    report = assess_contexts(
        [ctx],
        {(ctx.source_key, ctx.candidate_key): evidence},
        rules_cfg=_rules_cfg(),
        llm=llm,
        cache=cache,
        template=_template(),
        max_llm_calls=5,
        dry_run=True,
    )
    assert report.n_api_calls == 0
    assert backend.calls == 0
    assert report.items[0].decision_path == "rules"


def test_missing_evidence_is_insufficient(tmp_path: Path) -> None:
    ctx = _ctx("calcium-citrate", "magnesium-citrate")
    cache = AssessmentCache(tmp_path / "phase6.json")
    report = assess_contexts(
        [ctx],
        {},  # no evidence lookup will resolve
        rules_cfg=_rules_cfg(),
        llm=None,
        cache=cache,
        template=None,
        max_llm_calls=0,
    )
    assert report.n_without_evidence == 1
    assert report.items[0].recommendation_class == "insufficient_evidence"
