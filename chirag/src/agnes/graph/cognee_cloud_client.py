"""Cognee Cloud connectivity via direct HTTP calls to ``/api/v1/*``.

The official ``cogwit-sdk`` (0.1.7) posts to ``/api/add`` with snake_case
JSON payloads, but the live Cognee Cloud API documented at
``https://docs.cognee.ai`` expects versioned paths (``/api/v1/add``,
``/api/v1/cognify``, ``/api/v1/search``), camelCase field names
(``datasetName``, ``datasetIds``, ``searchType``, ...), and
``multipart/form-data`` for ``/add``. Talking to the SDK produced a
409 ``Either datasetId or datasetName must be provided.`` (verified by
runtime tracing in `.cursor/debug-98e52b.log`).

This module calls the API directly, normalizing responses to small
Pydantic models so downstream scripts see a stable interface.
"""

from __future__ import annotations

import asyncio
import json as _json
import os
import time
from typing import Any
from uuid import UUID

import aiohttp
from pydantic import BaseModel, ConfigDict

from agnes.config.settings import Settings
from agnes.models.graph import KGEdge, KGNode
from agnes.utils.logging import get_logger

log = get_logger(__name__)

_ENV_API_KEY = "COGWIT_API_KEY"
_ENV_BASE_URL = "COGWIT_API_BASE"
_DEFAULT_BASE_URL = "https://api.cognee.ai"


class CognneCloudError(RuntimeError):
    """Raised when a Cognee Cloud call returns a non-2xx response."""

    def __init__(self, op: str, status: int | str, error: Any):
        self.op = op
        self.status = status
        self.error = error
        super().__init__(f"cognee_cloud {op} failed ({status}): {error}")


class AddResult(BaseModel):
    """Normalized response from ``POST /api/v1/add`` (camelCase-tolerant)."""

    model_config = ConfigDict(extra="allow")

    status: str | None = None
    dataset_id: UUID | None = None
    pipeline_run_id: UUID | None = None
    dataset_name: str | None = None


def _resolve_api_key(settings: Settings) -> str | None:
    """Prefer AGNES_COGWIT_API_KEY; fall back to COGWIT_API_KEY."""
    if settings.cogwit_api_key:
        return settings.cogwit_api_key
    env_key = os.getenv(_ENV_API_KEY)
    return env_key or None


def _resolve_base_url(settings: Settings) -> str:
    if settings.cogwit_base_url:
        return settings.cogwit_base_url.rstrip("/")
    env = os.getenv(_ENV_BASE_URL)
    if env:
        return env.rstrip("/")
    return _DEFAULT_BASE_URL


class HttpTransport:
    """Thin aiohttp wrapper around Cognee Cloud's versioned endpoints."""

    def __init__(self, base_url: str, api_key: str, *, timeout_s: float = 7200.0):
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = aiohttp.ClientTimeout(total=timeout_s, sock_connect=30)

    def _headers(self, *, json_body: bool) -> dict[str, str]:
        h = {"X-Api-Key": self._api_key}
        if json_body:
            h["Content-Type"] = "application/json"
        return h

    async def post_json(self, path: str, payload: dict[str, Any]) -> Any:
        url = f"{self.base_url}{path}"
        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            async with session.post(
                url, json=payload, headers=self._headers(json_body=True)
            ) as resp:
                body = await _read_body(resp)
                if resp.status < 200 or resp.status >= 300:
                    raise CognneCloudError(path, resp.status, body)
                return body

    async def post_multipart(self, path: str, form: aiohttp.FormData) -> Any:
        url = f"{self.base_url}{path}"
        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            async with session.post(
                url, data=form, headers=self._headers(json_body=False)
            ) as resp:
                body = await _read_body(resp)
                if resp.status < 200 or resp.status >= 300:
                    raise CognneCloudError(path, resp.status, body)
                return body


async def _read_body(resp: aiohttp.ClientResponse) -> Any:
    ctype = resp.headers.get("Content-Type", "")
    if "application/json" in ctype:
        return await resp.json()
    text = await resp.text()
    try:
        return _json.loads(text)
    except Exception:
        return text


def _preview(body: Any) -> Any:
    if isinstance(body, str):
        return body[:400]
    try:
        return _json.loads(_json.dumps(body, default=str))[:400] if isinstance(body, list) else body
    except Exception:
        return str(body)[:400]


def build_transport(settings: Settings) -> HttpTransport:
    """Resolve key + base URL and return a configured :class:`HttpTransport`."""
    api_key = _resolve_api_key(settings)
    if not api_key:
        raise CognneCloudError(
            "init",
            "config",
            "AGNES_COGWIT_API_KEY (or COGWIT_API_KEY) is not set",
        )
    base_url = _resolve_base_url(settings)
    return HttpTransport(base_url, api_key)


def _fmt_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    return str(value)


def _node_sentence(node: KGNode) -> str:
    props = node.props or {}
    parts = [f"Node {node.id} is a {node.kind}"]
    if props:
        attrs = ", ".join(f"{k}={_fmt_value(v)}" for k, v in sorted(props.items()))
        parts.append(f"with attributes {attrs}")
    return ". ".join(parts) + "."


def _edge_sentence(edge: KGEdge) -> str:
    props = edge.props or {}
    sentence = f"{edge.source} {edge.kind} {edge.target}"
    if props:
        attrs = ", ".join(f"{k}={_fmt_value(v)}" for k, v in sorted(props.items()))
        sentence += f" ({attrs})"
    return sentence + "."


def serialize_graph(nodes: list[KGNode], edges: list[KGEdge]) -> list[str]:
    """Serialize a Phase 3 graph payload into deterministic fact sentences."""
    out: list[str] = []
    for node in nodes:
        out.append(_node_sentence(node))
    for edge in edges:
        out.append(_edge_sentence(edge))
    return out


def _parse_add_result(body: Any) -> AddResult:
    """Tolerate both snake_case and camelCase response keys from ``/api/v1/add``."""
    if not isinstance(body, dict):
        return AddResult()

    def pick(*keys: str) -> Any:
        for k in keys:
            if k in body and body[k] not in (None, ""):
                return body[k]
        return None

    def as_uuid(value: Any) -> UUID | None:
        if value is None:
            return None
        try:
            return UUID(str(value))
        except Exception:
            return None

    return AddResult(
        status=pick("status"),
        dataset_id=as_uuid(pick("dataset_id", "datasetId")),
        pipeline_run_id=as_uuid(pick("pipeline_run_id", "pipelineRunId")),
        dataset_name=pick("dataset_name", "datasetName"),
    )


class CognneCloudClient:
    """Async Cognee Cloud client speaking the documented ``/api/v1/*`` surface."""

    def __init__(self, settings: Settings, *, transport: HttpTransport | None = None):
        self.settings = settings
        self._t = transport or build_transport(settings)

    @property
    def transport(self) -> HttpTransport:
        return self._t

    async def add_text(
        self,
        text: str | list[str],
        *,
        dataset_name: str | None = None,
        dataset_id: UUID | None = None,
        node_set: list[str] | None = None,
        filename: str = "agnes.txt",
    ) -> AddResult:
        """POST ``/api/v1/add`` as multipart/form-data with one or more text parts."""
        dataset = dataset_name or self.settings.cogwit_dataset
        items = [text] if isinstance(text, str) else list(text)
        log.info("cogwit.add_text", dataset=dataset, items=len(items))

        form = aiohttp.FormData()
        for item in items:
            form.add_field(
                "data",
                item,
                filename=filename,
                content_type="text/plain",
            )
        if dataset_id is not None:
            form.add_field("datasetId", str(dataset_id))
        if dataset_name or dataset_id is None:
            form.add_field("datasetName", dataset)
        if node_set:
            for n in node_set:
                form.add_field("node_set", n)

        body = await self._t.post_multipart("/api/v1/add", form)
        return _parse_add_result(body)

    async def add_graph(
        self,
        nodes: list[KGNode],
        edges: list[KGEdge],
        *,
        dataset_name: str | None = None,
        batch_size: int = 500,
    ) -> list[AddResult]:
        """Upload a Phase 3 graph payload as batched text/plain parts."""
        sentences = serialize_graph(nodes, edges)
        dataset = dataset_name or self.settings.cogwit_dataset
        results: list[AddResult] = []
        if not sentences:
            log.warning("cogwit.add_graph.empty", dataset=dataset)
            return results

        dataset_id: UUID | None = None
        for start in range(0, len(sentences), batch_size):
            batch = sentences[start : start + batch_size]
            log.info(
                "cogwit.add_graph.batch",
                dataset=dataset,
                batch_start=start,
                batch_size=len(batch),
                total=len(sentences),
            )
            blob = "\n".join(batch)
            result = await self.add_text(
                blob,
                dataset_name=dataset,
                dataset_id=dataset_id,
                filename=f"agnes-graph-{start:06d}.txt",
            )
            results.append(result)
            dataset_id = result.dataset_id or dataset_id
        return results

    async def cognify(
        self,
        *,
        dataset_ids: list[UUID] | None = None,
        datasets: list[str] | None = None,
        run_in_background: bool = False,
    ) -> Any:
        if not dataset_ids and not datasets:
            datasets = [self.settings.cogwit_dataset]
        payload: dict[str, Any] = {"runInBackground": run_in_background}
        if dataset_ids:
            payload["datasetIds"] = [str(x) for x in dataset_ids]
        if datasets:
            payload["datasets"] = datasets
        log.info(
            "cogwit.cognify",
            dataset_ids=payload.get("datasetIds") or [],
            datasets=payload.get("datasets") or [],
            run_in_background=run_in_background,
        )
        return await self._t.post_json("/api/v1/cognify", payload)

    async def search(
        self,
        query_text: str,
        *,
        search_type: str = "GRAPH_COMPLETION",
        datasets: list[str] | None = None,
        dataset_ids: list[UUID] | None = None,
        top_k: int = 10,
        only_context: bool = False,
    ) -> Any:
        payload: dict[str, Any] = {
            "searchType": search_type,
            "query": query_text,
            "topK": top_k,
            "onlyContext": only_context,
        }
        if datasets:
            payload["datasets"] = datasets
        if dataset_ids:
            payload["datasetIds"] = [str(x) for x in dataset_ids]
        log.info("cogwit.search", search_type=search_type, query_chars=len(query_text))
        return await self._t.post_json("/api/v1/search", payload)

    async def ping(self) -> dict[str, Any]:
        """Round-trip a minimal add + cognify through Cognee Cloud."""
        dataset = self.settings.cogwit_dataset + "_smoke"
        start = time.perf_counter()
        try:
            added = await self.add_text(
                "Smoke test: procurement memory stores one sentence about raw materials.",
                dataset_name=dataset,
            )
            if added.dataset_id is not None:
                await self.cognify(dataset_ids=[added.dataset_id])
            else:
                await self.cognify(datasets=[dataset])
        except CognneCloudError as exc:
            return {
                "ok": False,
                "op": exc.op,
                "status": exc.status,
                "error": _preview(exc.error),
                "dataset": dataset,
            }
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc), "dataset": dataset}
        latency_ms = int((time.perf_counter() - start) * 1000)
        return {
            "ok": True,
            "latency_ms": latency_ms,
            "dataset": dataset,
            "dataset_id": str(added.dataset_id) if added.dataset_id else None,
        }


def ping(settings: Settings) -> dict[str, Any]:
    """Synchronous wrapper used by :mod:`scripts.smoke_cognee`."""
    try:
        client = CognneCloudClient(settings)
    except CognneCloudError as exc:
        return {"ok": False, "op": exc.op, "error": _preview(exc.error)}
    return asyncio.run(client.ping())
