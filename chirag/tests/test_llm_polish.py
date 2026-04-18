"""Phase 7 structured polish-LLM tests (backend stubbed)."""

from __future__ import annotations

import json
from typing import cast

import pytest

from agnes.config.settings import Settings
from agnes.recommendation.llm_polish import (
    RecommendationLLMError,
    StructuredBackend,
    StructuredResult,
    SummaryLLM,
)


class _Backend:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls = 0

    def generate(self, prompt: str, *, model: str) -> StructuredResult:
        self.calls += 1
        if not self._responses:
            raise AssertionError("no more scripted responses")
        return StructuredResult(text=self._responses.pop(0), model=model)


def _llm(backend: StructuredBackend) -> SummaryLLM:
    return SummaryLLM(
        Settings(openai_api_key="test"),
        model="gpt-4o-mini",
        backend=backend,
    )


def test_valid_json_is_parsed() -> None:
    payload = json.dumps(
        {"tradeoff_summary": "summary text", "risk_notes": ["note"]}
    )
    backend = _Backend([payload])
    result, raw = _llm(cast(StructuredBackend, backend)).polish("prompt")
    assert result.tradeoff_summary == "summary text"
    assert result.risk_notes == ["note"]
    assert raw == payload


def test_fenced_json_is_extracted() -> None:
    payload = (
        "```json\n"
        + json.dumps({"tradeoff_summary": "x", "risk_notes": []})
        + "\n```"
    )
    backend = _Backend([payload])
    parsed, _ = _llm(cast(StructuredBackend, backend)).polish("prompt")
    assert parsed.tradeoff_summary == "x"


def test_retries_once_on_malformed() -> None:
    good = json.dumps({"tradeoff_summary": "ok", "risk_notes": []})
    backend = _Backend(["garbage", good])
    parsed, _ = _llm(cast(StructuredBackend, backend)).polish("prompt")
    assert parsed.tradeoff_summary == "ok"
    assert backend.calls == 2


def test_raises_after_two_failures() -> None:
    backend = _Backend(["nope", "still nope"])
    with pytest.raises(RecommendationLLMError):
        _llm(cast(StructuredBackend, backend)).polish("prompt")


def test_raises_on_schema_mismatch() -> None:
    bad = json.dumps({"wrong_field": "x"})
    backend = _Backend([bad, bad])
    with pytest.raises(RecommendationLLMError):
        _llm(cast(StructuredBackend, backend)).polish("prompt")
