"""Shared OpenAI client factory + rate-limit helpers.

The OpenAI Python SDK raises :class:`openai.RateLimitError` for HTTP 429.
The server typically includes a ``Retry-After`` header (seconds). These
helpers expose:

- :func:`make_client` — construct an ``openai.OpenAI`` from an API key.
- :func:`is_rate_limited` — ``True`` for 429 / rate-limit style errors.
- :func:`retry_after_seconds` — parsed ``Retry-After`` header or ``None``.

The goal is that Phases 4/5/6/7 use identical exponential-backoff logic.
"""

from __future__ import annotations

import re
from typing import Any

try:
    import openai
    from openai import OpenAI
except ImportError as exc:  # pragma: no cover - dependency is declared
    raise RuntimeError(
        "openai is required for Agnes LLM calls. Install with `uv pip install openai`."
    ) from exc


__all__ = ["make_client", "is_rate_limited", "retry_after_seconds"]


def make_client(api_key: str) -> OpenAI:
    """Construct an OpenAI client from an API key.

    Kept as a thin wrapper so tests can monkeypatch this single entrypoint.
    """

    if not api_key:
        raise ValueError("OpenAI API key is required (AGNES_OPENAI_API_KEY)")
    return OpenAI(api_key=api_key)


def is_rate_limited(exc: BaseException) -> bool:
    """Return True for 429 / quota-style OpenAI errors.

    Handles typed ``openai.RateLimitError`` as well as generic ``APIStatusError``
    instances carrying ``status_code == 429``. Also matches message-level
    fallbacks for exotic exception types during tests.
    """

    if isinstance(exc, openai.RateLimitError):
        return True
    status = getattr(exc, "status_code", None)
    if status == 429:
        return True
    response = getattr(exc, "response", None)
    if response is not None and getattr(response, "status_code", None) == 429:
        return True
    text = str(exc)
    return bool(
        re.search(r"\b429\b", text)
        or re.search(r"rate[_ ]?limit", text, re.IGNORECASE)
        or re.search(r"insufficient_quota|resource_exhausted", text, re.IGNORECASE)
    )


def retry_after_seconds(exc: BaseException) -> float | None:
    """Parse the ``Retry-After`` header from an OpenAI exception, if present.

    Falls back to scraping patterns like ``"retry after 12s"`` from the error
    message. Returns ``None`` when no hint is found, in which case callers
    should apply a default backoff.
    """

    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None) if response is not None else None
    if headers:
        for key in ("retry-after", "Retry-After", "x-ratelimit-reset-requests"):
            try:
                raw = headers.get(key)  # type: ignore[union-attr]
            except Exception:
                raw = None
            if raw is None:
                continue
            try:
                return max(0.0, float(raw))
            except (TypeError, ValueError):
                continue

    body: Any = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error") or {}
        raw = err.get("retry_after") if isinstance(err, dict) else None
        if raw is not None:
            try:
                return max(0.0, float(raw))
            except (TypeError, ValueError):
                pass

    match = re.search(r"retry(?:\s+after)?\s+(\d+(?:\.\d+)?)\s*s", str(exc), re.IGNORECASE)
    if match:
        try:
            return max(0.0, float(match.group(1)))
        except ValueError:
            return None
    return None
