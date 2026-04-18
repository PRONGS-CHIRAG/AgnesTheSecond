"""
Gemini grounded-extraction adapter (Phase 5).

Wraps ``google.genai`` with the ``google_search`` tool and coerces the free-text
response into a Pydantic schema. ``google_search`` cannot be combined with
``response_schema`` on the Gemini API, so this module parses JSON out of the
generated text and validates it against the caller-provided model.

Tests inject a ``GroundedBackend`` stub; production uses ``GoogleGroundedBackend``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol, TypeVar
from urllib.parse import urlparse

import structlog
from pydantic import BaseModel, ValidationError

from agnes.config.settings import Settings
from agnes.models.evidence import CitationRef

logger = structlog.get_logger(__name__)

DEFAULT_GROUNDED_MODEL = "gemini-2.5-flash"

T = TypeVar("T", bound=BaseModel)


class GroundedExtractionError(RuntimeError):
    """Raised when grounded extraction fails after the allowed retries."""


@dataclass(frozen=True)
class GroundedResult:
    """Raw grounded output: free text + parsed citations (before schema parse)."""

    text: str
    citations: list[CitationRef]
    model: str


class GroundedBackend(Protocol):
    """Minimal grounded-LLM interface. Tests inject their own implementation."""

    def generate(self, prompt: str, *, model: str) -> GroundedResult: ...


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(?P<body>\{.*?\})\s*```", re.DOTALL)
_BARE_JSON_RE = re.compile(r"(?P<body>\{.*\})", re.DOTALL)


def _extract_json_block(text: str) -> str:
    """Return the first JSON object found in ``text`` (fenced or bare)."""
    m = _JSON_FENCE_RE.search(text)
    if m:
        return m.group("body")
    m = _BARE_JSON_RE.search(text)
    if m:
        return m.group("body")
    return text.strip()


def _domain_of(url: str) -> str | None:
    try:
        host = urlparse(url).hostname
    except ValueError:
        return None
    if not host:
        return None
    return host.lower().lstrip(".")


def parse_citations(
    grounding_metadata: object,
    *,
    now: datetime | None = None,
) -> list[CitationRef]:
    """
    Convert a ``grounding_metadata`` object from google-genai into ``CitationRef``s.

    Accepts the Pydantic-like Gemini response object or a dict; tolerates missing
    fields. Deduplicates by URL, preserving first-seen order.
    """
    stamp = now or datetime.now(UTC)
    chunks = getattr(grounding_metadata, "grounding_chunks", None)
    if chunks is None and isinstance(grounding_metadata, dict):
        chunks = grounding_metadata.get("grounding_chunks") or grounding_metadata.get(
            "groundingChunks"
        )
    if not chunks:
        return []

    seen: set[str] = set()
    out: list[CitationRef] = []
    for ch in chunks:
        web = getattr(ch, "web", None)
        if web is None and isinstance(ch, dict):
            web = ch.get("web")
        if web is None:
            continue
        uri = getattr(web, "uri", None) or (web.get("uri") if isinstance(web, dict) else None)
        title = getattr(web, "title", None) or (
            web.get("title") if isinstance(web, dict) else None
        )
        if not uri or uri in seen:
            continue
        seen.add(uri)
        out.append(
            CitationRef(
                url=uri,
                title=title,
                domain=_domain_of(uri),
                retrieved_at=stamp,
            )
        )
    return out


class GoogleGroundedBackend:
    """Thin wrapper over ``google.genai.Client.models.generate_content`` + google_search."""

    def __init__(self, api_key: str | None) -> None:
        from google import genai

        self._genai = genai
        self._client = genai.Client(api_key=api_key) if api_key else genai.Client()

    def generate(self, prompt: str, *, model: str) -> GroundedResult:
        from google.genai import types

        tools = [types.Tool(google_search=types.GoogleSearch())]
        cfg = types.GenerateContentConfig(
            tools=tools,
            temperature=0.2,
            response_mime_type="text/plain",
        )
        resp = self._client.models.generate_content(
            model=model,
            contents=prompt,
            config=cfg,
        )
        text = resp.text or ""
        grounding_metadata: object = None
        candidates = getattr(resp, "candidates", None) or []
        if candidates:
            grounding_metadata = getattr(candidates[0], "grounding_metadata", None)
        citations = parse_citations(grounding_metadata)
        return GroundedResult(text=text, citations=citations, model=model)


class GroundedLLM:
    """
    Grounded-extraction client: calls a :class:`GroundedBackend`, parses the
    JSON payload against ``schema``, attaches grounding citations, and retries
    once on JSON/validation failure.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        model: str | None = None,
        backend: GroundedBackend | None = None,
    ) -> None:
        self.settings = settings
        self.model = model or getattr(
            settings, "phase5_grounded_model", DEFAULT_GROUNDED_MODEL
        )
        self._backend = backend

    def _ensure_backend(self) -> GroundedBackend:
        if self._backend is None:
            self._backend = GoogleGroundedBackend(api_key=self.settings.gemini_api_key)
        return self._backend

    def extract(
        self,
        prompt: str,
        *,
        schema: type[T],
        retries: int = 1,
    ) -> tuple[T, list[CitationRef], str]:
        """
        Run a grounded extraction and validate the JSON payload against ``schema``.

        Returns ``(parsed_model, citations, raw_text)``. Raises
        :class:`GroundedExtractionError` after ``retries`` failed attempts.
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
                    "phase5_grounded_json_parse_failed",
                    attempt=attempt + 1,
                    model=self.model,
                    err=str(exc)[:200],
                )
                continue
            try:
                parsed = schema.model_validate(payload)
            except ValidationError as exc:
                last_err = exc
                logger.warning(
                    "phase5_grounded_schema_validation_failed",
                    attempt=attempt + 1,
                    model=self.model,
                    err=str(exc)[:200],
                )
                continue
            return parsed, result.citations, result.text
        raise GroundedExtractionError(
            f"grounded extraction failed after {attempts} attempts: {last_err}"
        )
