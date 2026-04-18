"""Phase 6 structured LLM parse/retry behavior (no network)."""

from __future__ import annotations

import json
from typing import cast

import pytest

from agnes.config.settings import Settings
from agnes.models.assessment import SubstituteAssessmentLLM
from agnes.reasoning.llm_fallback import (
    AssessmentLLMError,
    StructuredBackend,
    StructuredLLM,
    StructuredResult,
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


def _llm(backend: StructuredBackend) -> StructuredLLM:
    return StructuredLLM(
        Settings(openai_api_key="test-key"),
        model="gpt-4o-mini",
        backend=backend,
    )


def _valid_json() -> str:
    payload = {
        "recommendation_class": "recommend_with_caveats",
        "rationale": "supports with caveats",
        "caveats": ["pilot scale"],
        "missing_information": ["certification"],
    }
    return json.dumps(payload)


def test_structured_llm_parses_valid_json() -> None:
    backend = _ScriptedBackend([_valid_json()])
    parsed, raw = _llm(cast(StructuredBackend, backend)).assess("prompt")
    assert isinstance(parsed, SubstituteAssessmentLLM)
    assert parsed.recommendation_class == "recommend_with_caveats"
    assert parsed.caveats == ["pilot scale"]
    assert backend.calls == 1
    assert raw.startswith("{")


def test_structured_llm_retries_on_malformed_json() -> None:
    backend = _ScriptedBackend(["not json at all", _valid_json()])
    parsed, _ = _llm(cast(StructuredBackend, backend)).assess("prompt")
    assert parsed.rationale == "supports with caveats"
    assert backend.calls == 2


def test_structured_llm_extracts_fenced_json() -> None:
    fenced = f"```json\n{_valid_json()}\n```"
    backend = _ScriptedBackend([fenced])
    parsed, _ = _llm(cast(StructuredBackend, backend)).assess("prompt")
    assert parsed.recommendation_class == "recommend_with_caveats"


def test_structured_llm_raises_after_two_failures() -> None:
    backend = _ScriptedBackend(["still not json", "also not json"])
    with pytest.raises(AssessmentLLMError):
        _llm(cast(StructuredBackend, backend)).assess("prompt")
    assert backend.calls == 2


def test_structured_llm_rejects_wrong_schema() -> None:
    """Parses but fails validation → retry; second bad response raises."""
    bad = json.dumps({"recommendation_class": "not_a_real_class", "rationale": "x"})
    backend = _ScriptedBackend([bad, bad])
    with pytest.raises(AssessmentLLMError):
        _llm(cast(StructuredBackend, backend)).assess("prompt")
    assert backend.calls == 2
