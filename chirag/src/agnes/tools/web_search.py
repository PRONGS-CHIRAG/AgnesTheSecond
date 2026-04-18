"""Web search adapter backing the Phase 5 ``search_web`` function-calling tool.

The LLM never hits an HTTP client directly. It calls ``search_web(query,
max_results)`` and the orchestration loop in
:mod:`agnes.retrieval.openai_grounded` dispatches the call through a
:class:`WebSearchProvider` Protocol. The default production provider is
:class:`TavilySearchProvider`; tests inject a fake list-returning stub.

Design goals:
- single ``search`` method, no streaming
- respect a client-side RPM cap so Tavily's free tier does not 429
- transparent retry on 429 using ``Retry-After`` when present
- structured logging + typed exceptions so the enricher can fail gracefully
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Protocol

import httpx
import structlog

logger = structlog.get_logger(__name__)

TAVILY_URL = "https://api.tavily.com/search"
TAVILY_RPM = int(os.environ.get("AGNES_TAVILY_RPM", "30"))
TAVILY_MAX_RETRIES = int(os.environ.get("AGNES_TAVILY_MAX_RETRIES", "4"))
TAVILY_TIMEOUT_SECONDS = float(os.environ.get("AGNES_TAVILY_TIMEOUT_SECONDS", "20"))


class WebSearchError(RuntimeError):
    """Raised when a web-search provider fails after the allowed retries."""


@dataclass(frozen=True)
class SearchHit:
    """One external search result surfaced to the grounded LLM loop."""

    url: str
    title: str
    snippet: str


class WebSearchProvider(Protocol):
    """Minimal interface the Phase 5 grounded loop depends on."""

    def search(self, query: str, max_results: int = 5) -> list[SearchHit]:  # noqa: D401
        ...


class TavilySearchProvider:
    """Tavily Search implementation of :class:`WebSearchProvider`.

    Uses the public ``/search`` endpoint with ``search_depth="basic"``. Runs a
    client-side RPM throttle + 429-aware retry loop so quota exhaustion is
    reported via :class:`WebSearchError` rather than a raw HTTP exception.
    """

    def __init__(
        self,
        api_key: str | None,
        *,
        client: httpx.Client | None = None,
        url: str = TAVILY_URL,
        rpm: int = TAVILY_RPM,
        max_retries: int = TAVILY_MAX_RETRIES,
        timeout_seconds: float = TAVILY_TIMEOUT_SECONDS,
    ) -> None:
        if not api_key:
            raise WebSearchError(
                "Tavily API key is required (AGNES_TAVILY_API_KEY) for Phase 5 grounding"
            )
        self._api_key = api_key
        self._url = url
        self._rpm = rpm
        self._max_retries = max_retries
        self._client = client or httpx.Client(timeout=timeout_seconds)
        self._request_ts: list[float] = []

    def _throttle(self) -> None:
        if self._rpm <= 0:
            return
        now = time.monotonic()
        window = 60.0
        self._request_ts = [ts for ts in self._request_ts if now - ts < window]
        if len(self._request_ts) >= self._rpm:
            sleep_for = window - (now - self._request_ts[0]) + 0.5
            if sleep_for > 0:
                logger.info(
                    "phase5_search_rate_pause",
                    sleep_seconds=round(sleep_for, 2),
                    window_requests=len(self._request_ts),
                )
                time.sleep(sleep_for)
                now = time.monotonic()
                self._request_ts = [ts for ts in self._request_ts if now - ts < window]
        self._request_ts.append(now)

    @staticmethod
    def _retry_after_from(resp: httpx.Response) -> float:
        raw = resp.headers.get("retry-after") or resp.headers.get("Retry-After")
        if raw:
            try:
                return max(0.0, float(raw))
            except ValueError:
                pass
        return 10.0

    def search(self, query: str, max_results: int = 5) -> list[SearchHit]:
        """Run one Tavily search and return a list of :class:`SearchHit`.

        Retries up to ``AGNES_TAVILY_MAX_RETRIES`` times on HTTP 429, honoring
        the ``Retry-After`` header when present.
        """

        if not query.strip():
            return []
        payload = {
            "api_key": self._api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": max(1, min(int(max_results), 10)),
            "include_answer": False,
            "include_raw_content": False,
        }

        attempt = 0
        while True:
            self._throttle()
            try:
                resp = self._client.post(self._url, json=payload)
            except httpx.HTTPError as exc:
                if attempt >= self._max_retries:
                    logger.exception("phase5_search_transport_failed", query=query[:200])
                    raise WebSearchError(f"tavily transport error: {exc}") from exc
                delay = min(30.0, 5.0 * (attempt + 1))
                logger.warning(
                    "phase5_search_transport_retry",
                    attempt=attempt + 1,
                    sleep_seconds=delay,
                    err=str(exc)[:200],
                )
                time.sleep(delay)
                attempt += 1
                continue

            if resp.status_code == 429:
                if attempt >= self._max_retries:
                    raise WebSearchError(
                        f"tavily rate-limited after {attempt + 1} attempts"
                    )
                delay = self._retry_after_from(resp)
                delay = min(max(delay + 1.0, 5.0), 90.0)
                logger.warning(
                    "phase5_search_rate_limited",
                    attempt=attempt + 1,
                    sleep_seconds=round(delay, 2),
                )
                time.sleep(delay)
                attempt += 1
                continue

            if resp.status_code >= 400:
                body = resp.text[:500] if resp.text else ""
                raise WebSearchError(
                    f"tavily http {resp.status_code}: {body}"
                )

            try:
                data = resp.json()
            except ValueError as exc:
                raise WebSearchError(f"tavily non-json response: {exc}") from exc

            results = data.get("results") if isinstance(data, dict) else None
            hits: list[SearchHit] = []
            if isinstance(results, list):
                for r in results:
                    if not isinstance(r, dict):
                        continue
                    url = str(r.get("url") or "").strip()
                    if not url:
                        continue
                    title = str(r.get("title") or url).strip()
                    snippet = str(r.get("content") or r.get("snippet") or "").strip()
                    hits.append(SearchHit(url=url, title=title, snippet=snippet))
            return hits
