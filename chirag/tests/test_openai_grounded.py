"""Unit tests for the Phase 5 OpenAI grounded retrieval adapter."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from agnes.config.settings import Settings
from agnes.models.evidence import SubstituteEvidenceLLM
from agnes.retrieval.openai_grounded import (
    GroundedExtractionError,
    GroundedLLM,
    GroundedResult,
    OpenAIGroundedBackend,
    _domain_of,
    _extract_json_block,
    urls_to_citations,
)
from agnes.tools.web_search import SearchHit, WebSearchProvider


def test_domain_of_returns_hostname() -> None:
    assert _domain_of("https://www.Example.com/x/y?q=1") == "www.example.com"
    assert _domain_of("no-scheme") is None


def test_urls_to_citations_deduplicates_and_stamps() -> None:
    now = datetime(2026, 4, 18, 12, 0, tzinfo=UTC)
    urls = [
        "https://a.example.com/1",
        "https://a.example.com/1",
        "https://b.example.com/x",
    ]
    titles = {
        "https://a.example.com/1": "Page A",
        "https://b.example.com/x": "Page B",
    }
    cites = urls_to_citations(urls, titles=titles, now=now)
    assert [c.url for c in cites] == [
        "https://a.example.com/1",
        "https://b.example.com/x",
    ]
    assert all(c.retrieved_at == now for c in cites)
    assert cites[0].domain == "a.example.com"
    assert cites[0].title == "Page A"


def test_urls_to_citations_empty_on_missing_input() -> None:
    assert urls_to_citations([]) == []


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
        Settings(openai_api_key="x"),
        model="gpt-4o-mini",
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
        Settings(openai_api_key="x"),
        model="gpt-4o-mini",
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
        Settings(openai_api_key="x"),
        model="gpt-4o-mini",
        backend=backend,
    )
    with pytest.raises(GroundedExtractionError):
        llm.extract("prompt", schema=SubstituteEvidenceLLM, retries=1)
    assert backend.calls == 2


class _FakeSearchProvider(WebSearchProvider):
    def __init__(self, hits: list[SearchHit]) -> None:
        self._hits = hits
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, max_results: int = 5) -> list[SearchHit]:
        self.calls.append((query, max_results))
        return self._hits


class _StubOpenAIClient:
    """Emits one tool call then a final JSON message."""

    def __init__(self, tool_call_args: dict[str, object], final_text: str) -> None:
        self._tool_call_args = tool_call_args
        self._final_text = final_text
        self._step = 0
        self.messages_log: list[list[dict[str, object]]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, *, model: str, messages, tools, tool_choice, temperature):
        self.messages_log.append(list(messages))
        if self._step == 0:
            self._step += 1
            tool_call = SimpleNamespace(
                id="call_1",
                type="function",
                function=SimpleNamespace(
                    name="search_web",
                    arguments=json.dumps(self._tool_call_args),
                ),
            )
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=None,
                            tool_calls=[tool_call],
                        )
                    )
                ]
            )
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=self._final_text,
                        tool_calls=None,
                    )
                )
            ]
        )


def test_openai_grounded_backend_runs_tool_loop() -> None:
    hits = [
        SearchHit(
            url="https://a.example.com/one",
            title="One",
            snippet="snippet one",
        ),
        SearchHit(
            url="https://b.example.com/two",
            title="Two",
            snippet="snippet two",
        ),
    ]
    search = _FakeSearchProvider(hits)
    backend = OpenAIGroundedBackend.__new__(OpenAIGroundedBackend)
    backend._client = _StubOpenAIClient(
        tool_call_args={"query": "calcium citrate suppliers", "max_results": 3},
        final_text=_good_payload(),
    )
    backend._search = search
    backend._max_tool_calls = 3
    backend._request_ts = []

    result = backend.generate("ignored-prompt", model="gpt-4o-mini")

    assert search.calls == [("calcium citrate suppliers", 3)]
    assert result.model == "gpt-4o-mini"
    assert result.text == _good_payload()
    assert [c.url for c in result.citations] == [
        "https://a.example.com/one",
        "https://b.example.com/two",
    ]
    assert result.citations[0].title == "One"


def test_openai_grounded_backend_honors_tool_budget() -> None:
    class _AlwaysToolClient:
        def __init__(self) -> None:
            self.calls = 0
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

        def _create(self, **kwargs):
            self.calls += 1
            tool_call = SimpleNamespace(
                id=f"call_{self.calls}",
                type="function",
                function=SimpleNamespace(
                    name="search_web",
                    arguments=json.dumps({"query": f"q{self.calls}"}),
                ),
            )
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=None,
                            tool_calls=[tool_call],
                        )
                    )
                ]
            )

    backend = OpenAIGroundedBackend.__new__(OpenAIGroundedBackend)
    stub = _AlwaysToolClient()
    backend._client = stub
    backend._search = _FakeSearchProvider([])
    backend._max_tool_calls = 2
    backend._request_ts = []

    result = backend.generate("ignored", model="gpt-4o-mini")
    assert result.text == ""
    assert stub.calls == backend._max_tool_calls + 1
