"""
OpenAI grounded-extraction adapter (Phase 5).

Wraps ``openai.chat.completions.create`` with a single ``search_web``
function-calling tool backed by a :class:`WebSearchProvider` (Tavily in
production). The adapter runs a bounded tool-calling loop:

1. Send the user prompt + tool spec.
2. If the model returns ``tool_calls``, dispatch each call to the search
   provider, append ``{role: "tool"}`` messages with the JSON-serialized
   hits, and accumulate the URLs actually surfaced to the model.
3. Once the model replies without a tool call, parse its text as JSON and
   validate it against the caller-supplied Pydantic schema.

URLs the model consumed become :class:`CitationRef` objects; no
``grounding_metadata`` equivalent exists on OpenAI, so
:func:`urls_to_citations` handles that translation.

Tests inject a ``GroundedBackend`` stub; production uses
:class:`OpenAIGroundedBackend` wired to a real
:class:`WebSearchProvider`.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol, TypeVar
from urllib.parse import urlparse

import structlog
from pydantic import BaseModel, ValidationError

from agnes.config.settings import Settings
from agnes.llm import is_rate_limited, make_client, retry_after_seconds
from agnes.models.evidence import CitationRef
from agnes.tools.web_search import SearchHit, TavilySearchProvider, WebSearchProvider

logger = structlog.get_logger(__name__)

DEFAULT_GROUNDED_MODEL = "gpt-4o-mini"

GROUNDED_MAX_RETRIES = int(os.environ.get("AGNES_GROUNDED_MAX_RETRIES", "6"))
GROUNDED_RPM = int(os.environ.get("AGNES_GROUNDED_RPM", "9"))
GROUNDED_MAX_TOOL_CALLS = int(os.environ.get("AGNES_GROUNDED_MAX_TOOL_CALLS", "4"))

T = TypeVar("T", bound=BaseModel)

SEARCH_TOOL_SPEC: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": (
                "Search the public web for evidence (title, url, snippet). "
                "Only cite URLs returned by this tool."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Keyword query to send to the web search backend.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Upper bound on returned hits (default 5).",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    }
]


class GroundedExtractionError(RuntimeError):
    """Raised when grounded extraction fails after the allowed retries."""


@dataclass(frozen=True)
class GroundedResult:
    """Raw grounded output: free text + citations from tool calls (pre-schema parse)."""

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


def urls_to_citations(
    urls: list[str],
    *,
    titles: dict[str, str] | None = None,
    now: datetime | None = None,
) -> list[CitationRef]:
    """Convert a list of URLs consumed by the LLM into :class:`CitationRef` objects.

    Deduplicates by URL while preserving first-seen order. Titles are looked up
    from the optional ``titles`` map (populated from ``search_web`` hits) and
    fall back to ``None``.
    """

    stamp = now or datetime.now(UTC)
    titles = titles or {}
    seen: set[str] = set()
    out: list[CitationRef] = []
    for raw in urls:
        if not raw:
            continue
        if raw in seen:
            continue
        seen.add(raw)
        out.append(
            CitationRef(
                url=raw,
                title=titles.get(raw),
                domain=_domain_of(raw),
                retrieved_at=stamp,
            )
        )
    return out


def _hits_to_tool_payload(hits: list[SearchHit]) -> str:
    return json.dumps(
        [{"url": h.url, "title": h.title, "snippet": h.snippet} for h in hits],
        ensure_ascii=False,
    )


class OpenAIGroundedBackend:
    """``openai.OpenAI`` wrapper that runs a bounded ``search_web`` tool loop."""

    def __init__(
        self,
        api_key: str | None,
        *,
        search_provider: WebSearchProvider | None = None,
        tavily_api_key: str | None = None,
        max_tool_calls: int = GROUNDED_MAX_TOOL_CALLS,
    ) -> None:
        self._client = make_client(api_key or "")
        self._search = search_provider or TavilySearchProvider(api_key=tavily_api_key)
        self._max_tool_calls = max(1, int(max_tool_calls))
        self._request_ts: list[float] = []

    def _throttle(self) -> None:
        if GROUNDED_RPM <= 0:
            return
        now = time.monotonic()
        window = 60.0
        self._request_ts = [ts for ts in self._request_ts if now - ts < window]
        if len(self._request_ts) >= GROUNDED_RPM:
            sleep_for = window - (now - self._request_ts[0]) + 0.5
            if sleep_for > 0:
                logger.info(
                    "phase5_grounded_rate_pause",
                    sleep_seconds=round(sleep_for, 2),
                    window_requests=len(self._request_ts),
                )
                time.sleep(sleep_for)
                now = time.monotonic()
                self._request_ts = [ts for ts in self._request_ts if now - ts < window]
        self._request_ts.append(now)

    def _chat_with_retry(
        self, *, model: str, messages: list[dict[str, Any]]
    ) -> Any:
        attempt = 0
        while True:
            self._throttle()
            try:
                return self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=SEARCH_TOOL_SPEC,
                    tool_choice="auto",
                    temperature=0.2,
                )
            except Exception as exc:
                if not is_rate_limited(exc) or attempt >= GROUNDED_MAX_RETRIES:
                    raise
                delay = retry_after_seconds(exc) or 20.0
                delay = min(max(delay + 1.0, 8.0), 120.0)
                logger.warning(
                    "phase5_grounded_rate_limited",
                    attempt=attempt + 1,
                    sleep_seconds=round(delay, 2),
                    model=model,
                )
                time.sleep(delay)
                attempt += 1

    def generate(self, prompt: str, *, model: str) -> GroundedResult:
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        consumed_urls: list[str] = []
        titles: dict[str, str] = {}

        for step in range(self._max_tool_calls + 1):
            resp = self._chat_with_retry(model=model, messages=messages)
            if not resp.choices:
                return GroundedResult(text="", citations=[], model=model)
            choice = resp.choices[0]
            message = choice.message
            tool_calls = getattr(message, "tool_calls", None) or []

            if not tool_calls:
                text = message.content or ""
                citations = urls_to_citations(consumed_urls, titles=titles)
                return GroundedResult(text=text, citations=citations, model=model)

            if step >= self._max_tool_calls:
                logger.warning(
                    "phase5_grounded_tool_budget_exhausted",
                    model=model,
                    max_tool_calls=self._max_tool_calls,
                )
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Tool-call budget exhausted. Reply now with the final JSON "
                            "object and do not call any more tools."
                        ),
                    }
                )
                continue

            messages.append(
                {
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments or "{}",
                            },
                        }
                        for tc in tool_calls
                    ],
                }
            )

            for tc in tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                if name != "search_web":
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(
                                {"error": f"unknown tool '{name}'"},
                                ensure_ascii=False,
                            ),
                        }
                    )
                    continue
                query = str(args.get("query") or "").strip()
                try:
                    max_results = int(args.get("max_results", 5))
                except (TypeError, ValueError):
                    max_results = 5
                try:
                    hits = self._search.search(query, max_results=max_results)
                except Exception as exc:
                    logger.warning(
                        "phase5_search_tool_failed",
                        query=query[:200],
                        err=str(exc)[:200],
                    )
                    hits = []
                for h in hits:
                    if h.url not in titles:
                        titles[h.url] = h.title
                    if h.url not in consumed_urls:
                        consumed_urls.append(h.url)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": _hits_to_tool_payload(hits),
                    }
                )

        return GroundedResult(
            text="",
            citations=urls_to_citations(consumed_urls, titles=titles),
            model=model,
        )


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
            self._backend = OpenAIGroundedBackend(
                api_key=self.settings.openai_api_key,
                tavily_api_key=self.settings.tavily_api_key,
            )
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
