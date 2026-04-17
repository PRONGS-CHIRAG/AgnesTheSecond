"""Cognee connectivity: local store + LLM via LiteLLM (Gemini) + FastEmbed embeddings."""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any

from agnes.config.settings import Settings


def _configure_cognee(settings: Settings) -> Any:
    """Import and configure Cognee (side-effect: logging, DB paths)."""
    # Reduce friction for local smoke tests (no FastAPI backend).
    os.environ.setdefault("ENABLE_BACKEND_ACCESS_CONTROL", "false")

    import cognee  # noqa: PLC0415 — defer heavy import until needed

    root = settings.cognee_data_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    cognee.config.system_root_directory(str(root))

    # LiteLLM routing: gemini/<model> with Google AI Studio key.
    model = settings.gemini_model
    if "/" not in model:
        llm_model = f"gemini/{model}"
    else:
        llm_model = model

    cognee.config.set_llm_provider("litellm")
    cognee.config.set_llm_model(llm_model)
    cognee.config.set_llm_api_key(settings.gemini_api_key)

    cognee.config.set_embedding_provider("fastembed")
    cognee.config.set_embedding_model("BAAI/bge-small-en-v1.5")
    cognee.config.set_embedding_dimensions(384)

    return cognee


async def _ping_async(settings: Settings) -> dict[str, Any]:
    cognee = _configure_cognee(settings)
    start = time.perf_counter()
    await cognee.add(
        "Smoke test: procurement memory stores one sentence about raw materials.",
        dataset_name="agnes_smoke",
    )
    await cognee.cognify(datasets=["agnes_smoke"])
    latency_ms = int((time.perf_counter() - start) * 1000)
    return {"ok": True, "latency_ms": latency_ms, "dataset": "agnes_smoke"}


def ping(settings: Settings) -> dict[str, Any]:
    """
    Run a minimal add + cognify pipeline against a local Cognee store.

    Requires AGNES_GEMINI_API_KEY and network access for Gemini + embedding model download
    (first run may be slower).
    """
    if not settings.gemini_api_key:
        return {
            "ok": False,
            "error": "AGNES_GEMINI_API_KEY is not set",
        }
    try:
        return asyncio.run(_ping_async(settings))
    except Exception as exc:  # noqa: BLE001 — smoke script surfaces any failure
        return {"ok": False, "error": str(exc)}
