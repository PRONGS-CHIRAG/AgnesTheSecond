"""Unit tests for the Phase 5 grounded retrieval adapter."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from agnes.config.settings import Settings
from agnes.models.evidence import SubstituteEvidenceLLM
from agnes.retrieval.gemini_grounded import (
    GroundedExtractionError,
    GroundedLLM,
    GroundedResult,
    _domain_of,
    _extract_json_block,
    parse_citations,
)


class _FakeWeb:
    def __init__(self, uri: str, title: str | None = None) -> None:
        self.uri = uri
        self.title = title


class _FakeChunk:
    def __init__(self, uri: str, title: str | None = None) -> None:
        self.web = _FakeWeb(uri, title)


class _FakeGroundingMetadata:
    def __init__(self, chunks: list[_FakeChunk]) -> None:
        self.grounding_chunks = chunks


def test_domain_of_returns_hostname() -> None:
    assert _domain_of("https://www.Example.com/x/y?q=1") == "www.example.com"
    assert _domain_of("no-scheme") is None


def test_parse_citations_deduplicates_and_stamps() -> None:
    meta = _FakeGroundingMetadata(
        [
            _FakeChunk("https://a.example.com/1", "Page A"),
            _FakeChunk("https://a.example.com/1", "Page A dup"),
            _FakeChunk("https://b.example.com/x", None),
        ]
    )
    now = datetime(2026, 4, 18, 12, 0, tzinfo=UTC)
    cites = parse_citations(meta, now=now)
    assert [c.url for c in cites] == [
        "https://a.example.com/1",
        "https://b.example.com/x",
    ]
    assert all(c.retrieved_at == now for c in cites)
    assert cites[0].domain == "a.example.com"


def test_parse_citations_handles_dict_shape() -> None:
    meta = {"grounding_chunks": [{"web": {"uri": "https://c.example.com/p", "title": "C"}}]}
    cites = parse_citations(meta)
    assert len(cites) == 1
    assert cites[0].url == "https://c.example.com/p"
    assert cites[0].title == "C"


def test_parse_citations_empty_on_missing_metadata() -> None:
    assert parse_citations(None) == []
    assert parse_citations({}) == []


def test_extract_json_block_handles_fenced_and_bare() -> None:
    fenced = "Some preamble\n```json\n{\"claims\": []}\n```\nsome trailer"
    assert _extract_json_block(fenced) == '{"claims": []}'

    bare = 'prefix {"claims": [{"key": "certification"}]} suffix'
    assert _extract_json_block(bare).startswith("{")


class _Backend:
    def __init__(self, outputs: list[GroundedResult]) -> None:
        self._outputs = list(outputs)
        self.calls = 0

    def generate(self, prompt: str, *, model: str) -> GroundedResult:
        self.calls += 1
        if not self._outputs:
            msg = "no more outputs"
            raise AssertionError(msg)
        return self._outputs.pop(0)


def _good_payload() -> str:
    payload = SubstituteEvidenceLLM(
        claims=[
            {
                "key": "functional_equivalence",
                "value": "ok",
                "polarity": "supports",
                "confidence": 0.5,
                "citations": [],
                "grounding_strength": "parametric",
            }
        ]
    )
    return payload.model_dump_json()


def test_grounded_llm_parses_valid_json() -> None:
    backend = _Backend(
        [GroundedResult(text=_good_payload(), citations=[], model="m")]
    )
    llm = GroundedLLM(
        Settings(gemini_api_key="x"),
        model="gemini-2.5-flash",
        backend=backend,
    )
    parsed, citations, _ = llm.extract("prompt", schema=SubstituteEvidenceLLM)
    assert isinstance(parsed, SubstituteEvidenceLLM)
    assert parsed.claims[0].key == "functional_equivalence"
    assert citations == []
    assert backend.calls == 1


def test_grounded_llm_retries_once_then_succeeds() -> None:
    backend = _Backend(
        [
            GroundedResult(text="not a json object", citations=[], model="m"),
            GroundedResult(text=_good_payload(), citations=[], model="m"),
        ]
    )
    llm = GroundedLLM(
        Settings(gemini_api_key="x"),
        model="gemini-2.5-flash",
        backend=backend,
    )
    parsed, _, _ = llm.extract("prompt", schema=SubstituteEvidenceLLM, retries=1)
    assert isinstance(parsed, SubstituteEvidenceLLM)
    assert backend.calls == 2


def test_grounded_llm_raises_after_retries() -> None:
    backend = _Backend(
        [
            GroundedResult(text="still not json", citations=[], model="m"),
            GroundedResult(text="also not json", citations=[], model="m"),
        ]
    )
    llm = GroundedLLM(
        Settings(gemini_api_key="x"),
        model="gemini-2.5-flash",
        backend=backend,
    )
    with pytest.raises(GroundedExtractionError):
        llm.extract("prompt", schema=SubstituteEvidenceLLM, retries=1)
    assert backend.calls == 2
