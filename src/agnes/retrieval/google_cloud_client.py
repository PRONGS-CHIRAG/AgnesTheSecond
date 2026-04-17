"""Google Gemini API client (google-genai SDK)."""

import time
from typing import Any

from google import genai
from google.genai import types

from agnes.config.settings import Settings


def ping(settings: Settings) -> dict[str, Any]:
    """
    Minimal connectivity check: one short generation call.

    Returns a dict with ok, model, latency_ms, and optional error.
    """
    if not settings.gemini_api_key:
        return {
            "ok": False,
            "model": settings.gemini_model,
            "latency_ms": 0,
            "error": "AGNES_GEMINI_API_KEY is not set",
        }

    client = genai.Client(api_key=settings.gemini_api_key)
    model = settings.gemini_model

    start = time.perf_counter()
    try:
        response = client.models.generate_content(
            model=model,
            contents="Reply with exactly: ok",
            config=types.GenerateContentConfig(
                max_output_tokens=16,
                temperature=0.0,
            ),
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
    text = ""
    if response.text:
        text = response.text.strip()
    return {
        "ok": True,
        "model": model,
        "latency_ms": latency_ms,
        "response_preview": text[:200] if text else None,
    }
