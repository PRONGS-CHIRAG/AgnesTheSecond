"""OpenAI embedding client with on-disk cache (Phase 4)."""

from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path
from typing import Protocol

import structlog

from agnes.config.settings import Settings
from agnes.llm import is_rate_limited, make_client, retry_after_seconds

logger = structlog.get_logger(__name__)

DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_CACHE_PATH = Path(".cache/phase4_embeddings.json")

EMBED_RATE_LIMIT_PER_MIN = int(os.environ.get("AGNES_EMBED_RPM", "90"))
EMBED_MAX_RETRIES = int(os.environ.get("AGNES_EMBED_MAX_RETRIES", "6"))


class EmbeddingBackend(Protocol):
    """Minimal provider interface (OpenAI by default; tests inject their own)."""

    def embed_batch(self, texts: list[str], model: str) -> list[list[float]]:
        ...


class _OpenAIEmbeddingBackend:
    """Thin wrapper over ``openai.OpenAI.embeddings.create``."""

    def __init__(self, api_key: str | None) -> None:
        self._client = make_client(api_key or "")

    def embed_batch(self, texts: list[str], model: str) -> list[list[float]]:
        resp = self._client.embeddings.create(model=model, input=texts)
        return [list(d.embedding) for d in resp.data]


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity clamped to ``[0, 1]``."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    sim = dot / (na * nb)
    return max(0.0, min(1.0, (sim + 1.0) / 2.0))


class EmbeddingClient:
    """
    Cached OpenAI embedding client keyed by ``(model, canonical_key)``.

    Cache is a JSON file on disk; the in-memory copy is flushed via ``save()``.
    Network calls only happen for cache misses; tests inject a backend stub.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        model: str | None = None,
        cache_path: Path | None = None,
        backend: EmbeddingBackend | None = None,
    ) -> None:
        self.settings = settings
        self.model = model or os.environ.get(
            "AGNES_PHASE4_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL
        )
        self.cache_path = cache_path or DEFAULT_CACHE_PATH
        self._cache: dict[str, dict[str, list[float]]] = self._load_cache()
        self._backend = backend
        self._request_ts: list[float] = []

    def _load_cache(self) -> dict[str, dict[str, list[float]]]:
        if not self.cache_path.is_file():
            return {}
        try:
            raw = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("phase4_embed_cache_corrupt", path=str(self.cache_path))
            return {}
        out: dict[str, dict[str, list[float]]] = {}
        for model, entries in raw.items():
            if isinstance(entries, dict):
                out[model] = {k: list(v) for k, v in entries.items() if isinstance(v, list)}
        return out

    def save(self) -> None:
        """Persist the in-memory cache to ``self.cache_path`` (idempotent)."""
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(
            json.dumps(self._cache, sort_keys=True),
            encoding="utf-8",
        )

    def _ensure_backend(self) -> EmbeddingBackend:
        if self._backend is None:
            self._backend = _OpenAIEmbeddingBackend(api_key=self.settings.openai_api_key)
        return self._backend

    def get(self, canonical_key: str, text: str) -> list[float]:
        """Return the embedding for ``canonical_key`` (hits cache when possible)."""
        cache_model = self._cache.setdefault(self.model, {})
        if canonical_key in cache_model:
            logger.debug("phase4_embed_cache_hit", key=canonical_key, model=self.model)
            return cache_model[canonical_key]
        logger.debug("phase4_embed_cache_miss", key=canonical_key, model=self.model)
        backend = self._ensure_backend()
        vec = self._embed_with_retry(backend, [text])[0]
        cache_model[canonical_key] = vec
        return vec

    def get_batch(
        self, items: list[tuple[str, str]], *, batch_size: int = 32
    ) -> dict[str, list[float]]:
        """
        Return ``{canonical_key: embedding}`` for ``items`` using the cache + one
        backend call per batch of misses. Preserves deterministic order.
        """
        cache_model = self._cache.setdefault(self.model, {})
        out: dict[str, list[float]] = {}
        misses: list[tuple[str, str]] = []
        for key, text in items:
            if key in cache_model:
                out[key] = cache_model[key]
            else:
                misses.append((key, text))

        if misses:
            backend = self._ensure_backend()
            for i in range(0, len(misses), batch_size):
                chunk = misses[i : i + batch_size]
                texts = [t for _, t in chunk]
                vectors = self._embed_with_retry(backend, texts)
                for (key, _), vec in zip(chunk, vectors, strict=True):
                    cache_model[key] = vec
                    out[key] = vec
                # Persist after each successful batch so partial runs are never lost.
                try:
                    self.save()
                except OSError as exc:  # pragma: no cover - best-effort flush
                    logger.warning(
                        "phase4_embed_cache_save_failed",
                        error=str(exc),
                        path=str(self.cache_path),
                    )
        return out

    def _throttle(self) -> None:
        """Client-side RPM guard so we stay comfortably under free-tier limits."""
        if EMBED_RATE_LIMIT_PER_MIN <= 0:
            return
        now = time.monotonic()
        window = 60.0
        self._request_ts = [ts for ts in self._request_ts if now - ts < window]
        if len(self._request_ts) >= EMBED_RATE_LIMIT_PER_MIN:
            sleep_for = window - (now - self._request_ts[0]) + 0.5
            if sleep_for > 0:
                logger.info(
                    "phase4_embed_rate_pause",
                    sleep_seconds=round(sleep_for, 2),
                    window_requests=len(self._request_ts),
                )
                time.sleep(sleep_for)
                now = time.monotonic()
                self._request_ts = [ts for ts in self._request_ts if now - ts < window]
        self._request_ts.append(now)

    def _embed_with_retry(
        self, backend: EmbeddingBackend, texts: list[str]
    ) -> list[list[float]]:
        """Embed one batch, honoring 429 retry hints and persisting partial caches."""
        attempt = 0
        while True:
            self._throttle()
            try:
                return backend.embed_batch(texts, self.model)
            except Exception as exc:
                if not is_rate_limited(exc) or attempt >= EMBED_MAX_RETRIES:
                    logger.exception(
                        "phase4_embed_batch_failed",
                        model=self.model,
                        batch_size=len(texts),
                        attempt=attempt,
                    )
                    raise
                delay = retry_after_seconds(exc) or 15.0
                delay = min(max(delay + 1.0, 5.0), 90.0)
                logger.warning(
                    "phase4_embed_rate_limited",
                    attempt=attempt + 1,
                    sleep_seconds=round(delay, 2),
                    batch_size=len(texts),
                )
                time.sleep(delay)
                attempt += 1
