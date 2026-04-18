"""
Phase 6 structured-output LLM fallback.

Calls OpenAI ``chat.completions.create`` with ``response_format={"type":
"json_object"}`` (no tools — Phase 6 reasons over Phase 5 evidence rather
than doing fresh web lookups). Parses the JSON response into
:class:`SubstituteAssessmentLLM` with one retry on parse/validation
failure.

Tests inject a ``StructuredBackend`` stub; production wires
:class:`OpenAIStructuredBackend`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Protocol, TypeVar

import structlog
from pydantic import BaseModel, ValidationError

from agnes.config.settings import Settings
from agnes.llm import make_client
from agnes.models.assessment import SubstituteAssessmentLLM
from agnes.models.evidence import SubstituteEvidence

logger = structlog.get_logger(__name__)

DEFAULT_PROMPT_PATH = Path("prompts/assessment.md")
DEFAULT_MODEL = "gpt-4o-mini"

T = TypeVar("T", bound=BaseModel)


class AssessmentLLMError(RuntimeError):
    """Raised when structured assessment fails after the allowed retries."""


@dataclass(frozen=True)
class StructuredResult:
    """Raw structured-output text + model id."""

    text: str
    model: str


class StructuredBackend(Protocol):
    """Minimal structured-LLM interface. Tests inject their own implementation."""

    def generate(self, prompt: str, *, model: str) -> StructuredResult: ...


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(?P<body>\{.*?\})\s*```", re.DOTALL)
_BARE_JSON_RE = re.compile(r"(?P<body>\{.*\})", re.DOTALL)


def _extract_json_block(text: str) -> str:
    m = _JSON_FENCE_RE.search(text)
    if m:
        return m.group("body")
    m = _BARE_JSON_RE.search(text)
    if m:
        return m.group("body")
    return text.strip()


class OpenAIStructuredBackend:
    """``openai.OpenAI`` wrapper that forces JSON output via ``response_format``."""

    def __init__(self, api_key: str | None) -> None:
        self._client = make_client(api_key or "")

    def generate(self, prompt: str, *, model: str) -> StructuredResult:
        resp = self._client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content if resp.choices else ""
        return StructuredResult(text=content or "", model=model)


def load_prompt_template(path: Path | None = None) -> Template:
    """Load the Phase 6 assessment prompt template."""
    template_path = path or DEFAULT_PROMPT_PATH
    raw = template_path.read_text(encoding="utf-8")
    return Template(raw)


def render_prompt(
    template: Template,
    *,
    company: str,
    product: str,
    source_key: str,
    source_name: str,
    candidate_key: str,
    candidate_name: str,
    claims_json: str,
    rules_summary: str,
) -> str:
    """Fill the Phase 6 prompt template for one borderline tuple."""
    return template.safe_substitute(
        company=company,
        product=product,
        source_key=source_key,
        source_name=source_name,
        candidate_key=candidate_key,
        candidate_name=candidate_name,
        claims_json=claims_json,
        rules_summary=rules_summary,
    )


def claims_to_json(evidence: SubstituteEvidence) -> str:
    """Serialize claims to a human-readable JSON blob for the prompt."""
    payload = [
        {
            "key": c.key,
            "value": c.value,
            "polarity": c.polarity,
            "confidence": c.confidence,
            "grounding_strength": c.grounding_strength,
            "citations": [cite.url for cite in c.citations],
        }
        for c in evidence.claims
    ]
    return json.dumps(payload, indent=2)


class StructuredLLM:
    """
    Structured-assessment client: call backend, parse JSON, validate against
    :class:`SubstituteAssessmentLLM`, retry once on parse/validation failure.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        model: str | None = None,
        backend: StructuredBackend | None = None,
    ) -> None:
        self.settings = settings
        self.model = model or getattr(settings, "phase6_llm_model", DEFAULT_MODEL)
        self._backend = backend

    def _ensure_backend(self) -> StructuredBackend:
        if self._backend is None:
            self._backend = OpenAIStructuredBackend(
                api_key=self.settings.openai_api_key
            )
        return self._backend

    def assess(
        self,
        prompt: str,
        *,
        retries: int = 1,
    ) -> tuple[SubstituteAssessmentLLM, str]:
        """
        Run the structured assessment.

        Returns ``(parsed_model, raw_text)``. Raises :class:`AssessmentLLMError`
        after ``retries`` failed attempts.
        """
        backend = self._ensure_backend()
        last_err: Exception | None = None
        attempts = retries + 1
        for attempt in range(attempts):
            result = backend.generate(prompt, model=self.model)
            block = _extract_json_block(result.text)
            try:
                payload = json.loads(block)
            except json.JSONDecodeError as exc:
                last_err = exc
                logger.warning(
                    "phase6_llm_json_parse_failed",
                    attempt=attempt + 1,
                    model=self.model,
                    err=str(exc)[:200],
                )
                continue
            try:
                parsed = SubstituteAssessmentLLM.model_validate(payload)
            except ValidationError as exc:
                last_err = exc
                logger.warning(
                    "phase6_llm_schema_validation_failed",
                    attempt=attempt + 1,
                    model=self.model,
                    err=str(exc)[:200],
                )
                continue
            return parsed, result.text
        raise AssessmentLLMError(
            f"structured assessment failed after {attempts} attempts: {last_err}"
        )
