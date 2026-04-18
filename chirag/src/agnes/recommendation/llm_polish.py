"""
Phase 7 optional LLM polish for consolidation-opportunity summaries.

Mirrors the Phase 6 structured-output scaffold: call OpenAI
``chat.completions.create`` with ``response_format={"type": "json_object"}``
(no tools), parse the JSON reply into :class:`SummaryLLMResponse`, retry
once on parse/validation failure, raise :class:`RecommendationLLMError`
after the second failure.

The LLM never changes the grade, suppliers, or scoring — it only rewrites the
``tradeoff_summary`` and optionally surfaces structured ``risk_notes``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import Protocol

import structlog
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agnes.config.settings import Settings
from agnes.llm import make_client
from agnes.models.recommendation import ConsolidationOpportunity, SourcingRecommendation

logger = structlog.get_logger(__name__)

DEFAULT_PROMPT_PATH = Path("prompts/recommendation_polish.md")
DEFAULT_MODEL = "gpt-4o-mini"


class RecommendationLLMError(RuntimeError):
    """Raised when structured polish fails after the allowed retries."""


class SummaryLLMResponse(BaseModel):
    """LLM-facing contract for the polish pass."""

    model_config = ConfigDict(extra="forbid")

    tradeoff_summary: str = Field(min_length=1)
    risk_notes: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class StructuredResult:
    """Raw structured-output text + model id."""

    text: str
    model: str


class StructuredBackend(Protocol):
    """Minimal interface. Tests inject their own implementation."""

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
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content if resp.choices else ""
        return StructuredResult(text=content or "", model=model)


def load_prompt_template(path: Path | None = None) -> Template:
    """Load the Phase 7 polish prompt template."""
    template_path = path or DEFAULT_PROMPT_PATH
    raw = template_path.read_text(encoding="utf-8")
    return Template(raw)


def _format_list(items: list[str]) -> str:
    if not items:
        return "  (none)"
    return "\n".join(f"  - {x}" for x in items)


def render_prompt(
    template: Template,
    *,
    opportunity: ConsolidationOpportunity,
    top_rows: list[SourcingRecommendation],
) -> str:
    """Fill the Phase 7 polish prompt template."""
    caveats: list[str] = []
    contradictions: list[str] = []
    for row in top_rows:
        for cav in row.caveats:
            if cav not in caveats:
                caveats.append(cav)
        for note in row.risk_notes:
            if note.startswith("contradiction:") and note not in contradictions:
                contradictions.append(note)

    return template.safe_substitute(
        source_name=opportunity.source_display_name,
        candidate_name=opportunity.best_candidate_display_name,
        grade=opportunity.recommendation_grade,
        acceptability=(
            f"{(sum(r.acceptability for r in top_rows) / len(top_rows)):.2f}"
            if top_rows
            else "n/a"
        ),
        sourcing_benefit=f"{opportunity.aggregate_sourcing_benefit:.2f}",
        current_suppliers=", ".join(opportunity.unique_current_suppliers) or "none",
        recommended_suppliers=(
            ", ".join(opportunity.unique_recommended_suppliers) or "none"
        ),
        caveats=_format_list(caveats),
        contradictions=_format_list(contradictions),
    )


class SummaryLLM:
    """Structured polish client: call, parse JSON, validate, one retry."""

    def __init__(
        self,
        settings: Settings,
        *,
        model: str | None = None,
        backend: StructuredBackend | None = None,
    ) -> None:
        self.settings = settings
        self.model = model or getattr(settings, "phase7_llm_model", DEFAULT_MODEL)
        self._backend = backend

    def _ensure_backend(self) -> StructuredBackend:
        if self._backend is None:
            self._backend = OpenAIStructuredBackend(
                api_key=self.settings.openai_api_key
            )
        return self._backend

    def polish(
        self,
        prompt: str,
        *,
        retries: int = 1,
    ) -> tuple[SummaryLLMResponse, str]:
        """
        Run the polish pass. Returns ``(parsed_model, raw_text)``. Raises
        :class:`RecommendationLLMError` after ``retries + 1`` failed attempts.
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
                    "phase7_llm_json_parse_failed",
                    attempt=attempt + 1,
                    model=self.model,
                    err=str(exc)[:200],
                )
                continue
            try:
                parsed = SummaryLLMResponse.model_validate(payload)
            except ValidationError as exc:
                last_err = exc
                logger.warning(
                    "phase7_llm_schema_validation_failed",
                    attempt=attempt + 1,
                    model=self.model,
                    err=str(exc)[:200],
                )
                continue
            return parsed, result.text
        raise RecommendationLLMError(
            f"structured polish failed after {attempts} attempts: {last_err}"
        )
