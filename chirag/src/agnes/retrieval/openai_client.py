"""OpenAI connectivity ping (used by the smoke script)."""

from __future__ import annotations

import time
from typing import Any

from agnes.config.settings import Settings
from agnes.llm import make_client


def ping(settings: Settings) -> dict[str, Any]:
    """Minimal connectivity check: one short chat completion.

    Returns a dict with ``ok``, ``model``, ``latency_ms`` and optional ``error``.
    """
    if not settings.openai_api_key:
        return {
            "ok": False,
            "model": settings.openai_model,
            "latency_ms": 0,
            "error": "AGNES_OPENAI_API_KEY is not set",
        }

    client = make_client(settings.openai_api_key)
    model = settings.openai_model

    start = time.perf_counter()
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Reply with exactly: ok"}],
            max_tokens=8,
            temperature=0.0,
        )
    except Exception as exc:  # noqa: BLE001 — surface any API error in smoke output
        latency_ms = int((time.perf_counter() - start) * 1000)
        return {
            "ok": False,
            "model": model,
            "latency_ms": latency_ms,
            "error": str(exc),
        }

    latency_ms = int((time.perf_counter() - start) * 1000)
    text = (resp.choices[0].message.content or "").strip() if resp.choices else ""
    return {
        "ok": True,
        "model": model,
        "latency_ms": latency_ms,
        "response_preview": text[:200] if text else None,
    }
