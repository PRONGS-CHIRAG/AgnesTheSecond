"""Offline tests for the Cognee Cloud client and graph serializer."""

from __future__ import annotations

import asyncio
import os
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID

import aiohttp
import pytest

from agnes.config.settings import Settings
from agnes.graph.cognee_cloud_client import (
    CognneCloudClient,
    CognneCloudError,
    HttpTransport,
    _resolve_api_key,
    serialize_graph,
)
from agnes.models.graph import KGEdge, KGNode


def _settings(**overrides: Any) -> Settings:
    env_keep = {k: os.environ.get(k) for k in ("AGNES_COGWIT_API_KEY", "COGWIT_API_KEY")}
    for k in env_keep:
        os.environ.pop(k, None)
    try:
        s = Settings(**overrides)
    finally:
        for k, v in env_keep.items():
            if v is not None:
                os.environ[k] = v
    return s


class _FakeTransport:
    """In-memory double for :class:`HttpTransport` used in unit tests."""

    def __init__(
        self,
        *,
        multipart_result: Any = None,
        json_result: Any = None,
        multipart_side_effect: Any = None,
    ) -> None:
        self.multipart_calls: list[tuple[str, dict[str, Any]]] = []
        self.json_calls: list[tuple[str, dict[str, Any]]] = []
        self._multipart_result = multipart_result
        self._json_result = json_result
        self._multipart_side_effect = multipart_side_effect

    async def post_multipart(self, path: str, form: aiohttp.FormData) -> Any:
        fields = _extract_form_fields(form)
        self.multipart_calls.append((path, fields))
        if self._multipart_side_effect:
            return self._multipart_side_effect(path, fields)
        return self._multipart_result

    async def post_json(self, path: str, payload: dict[str, Any]) -> Any:
        self.json_calls.append((path, payload))
        return self._json_result


def _extract_form_fields(form: aiohttp.FormData) -> dict[str, Any]:
    """Extract name→value(s) from the protected ``_fields`` list for assertions."""
    result: dict[str, list[Any]] = {}
    for field in form._fields:  # type: ignore[attr-defined]
        type_options = field[0] if isinstance(field, tuple) else {}
        name = None
        value = None
        if isinstance(field, tuple) and len(field) >= 3:
            name = type_options.get("name")
            value = field[2]
        if name is None:
            continue
        result.setdefault(name, []).append(value)
    return {k: (v if len(v) > 1 else v[0]) for k, v in result.items()}


def _make_client(transport: Any, *, api_key: str = "k-test") -> CognneCloudClient:
    return CognneCloudClient(_settings(cogwit_api_key=api_key), transport=transport)


def _sample_graph() -> tuple[list[KGNode], list[KGEdge]]:
    nodes = [
        KGNode(id="Company:1", kind="Company", props={"name": "Acme"}),
        KGNode(
            id="CanonicalMaterial:calcium-citrate",
            kind="CanonicalMaterial",
            props={"canonical_key": "calcium-citrate", "ingredient_family": "minerals"},
        ),
    ]
    edges = [
        KGEdge(source="Company:1", target="RawProduct:7", kind="OWNS"),
        KGEdge(
            source="RawProduct:7",
            target="CanonicalMaterial:calcium-citrate",
            kind="INSTANCE_OF",
        ),
    ]
    return nodes, edges


def test_serialize_graph_is_deterministic() -> None:
    nodes, edges = _sample_graph()
    out_a = serialize_graph(nodes, edges)
    out_b = serialize_graph(nodes, edges)
    assert out_a == out_b
    assert len(out_a) == len(nodes) + len(edges)
    assert out_a[0] == "Node Company:1 is a Company. with attributes name=Acme."
    assert "Node CanonicalMaterial:calcium-citrate is a CanonicalMaterial" in out_a[1]
    assert out_a[2] == "Company:1 OWNS RawProduct:7."


def test_resolve_api_key_prefers_settings_then_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COGWIT_API_KEY", raising=False)
    monkeypatch.delenv("AGNES_COGWIT_API_KEY", raising=False)
    s_env_only = _settings()
    monkeypatch.setenv("COGWIT_API_KEY", "env-key")
    assert _resolve_api_key(s_env_only) == "env-key"

    s_override = _settings(cogwit_api_key="agnes-key")
    assert _resolve_api_key(s_override) == "agnes-key"


def test_client_without_api_key_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COGWIT_API_KEY", raising=False)
    monkeypatch.delenv("AGNES_COGWIT_API_KEY", raising=False)
    with pytest.raises(CognneCloudError) as excinfo:
        CognneCloudClient(_settings())
    assert excinfo.value.op == "init"


def test_add_text_hits_versioned_multipart_endpoint() -> None:
    uid = UUID("11111111-1111-1111-1111-111111111111")
    transport = _FakeTransport(
        multipart_result={
            "status": "DatasetCreated",
            "dataset_id": str(uid),
            "pipeline_run_id": "22222222-2222-2222-2222-222222222222",
            "dataset_name": "agnes",
        }
    )
    client = _make_client(transport)
    resp = asyncio.run(client.add_text("hello", dataset_name="agnes"))
    assert len(transport.multipart_calls) == 1
    path, fields = transport.multipart_calls[0]
    assert path == "/api/v1/add"
    assert fields["data"] == "hello"
    assert fields["datasetName"] == "agnes"
    assert resp.dataset_id == uid


def test_add_text_tolerates_camelcase_response() -> None:
    uid = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    transport = _FakeTransport(
        multipart_result={
            "status": "DatasetCreated",
            "datasetId": str(uid),
            "pipelineRunId": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            "datasetName": "agnes",
        }
    )
    client = _make_client(transport)
    resp = asyncio.run(client.add_text("hi"))
    assert resp.dataset_id == uid
    assert resp.dataset_name == "agnes"


def test_add_graph_batches_and_reuses_dataset_id() -> None:
    uid = UUID("33333333-3333-3333-3333-333333333333")

    def _side_effect(path: str, fields: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "DatasetUpdated",
            "dataset_id": str(uid),
            "pipeline_run_id": "44444444-4444-4444-4444-444444444444",
            "dataset_name": "agnes",
        }

    transport = _FakeTransport(multipart_side_effect=_side_effect)
    client = _make_client(transport)
    nodes = [
        KGNode(id=f"Company:{i}", kind="Company", props={"name": f"Co{i}"})
        for i in range(3)
    ]
    edges: list[KGEdge] = []
    responses = asyncio.run(
        client.add_graph(nodes, edges, dataset_name="agnes", batch_size=2)
    )
    assert len(responses) == 2
    assert len(transport.multipart_calls) == 2
    first_fields = transport.multipart_calls[0][1]
    second_fields = transport.multipart_calls[1][1]
    assert "datasetId" not in first_fields
    assert second_fields["datasetId"] == str(uid)


def test_cognify_uses_camelcase_payload() -> None:
    uid = UUID("99999999-9999-9999-9999-999999999999")
    transport = _FakeTransport(json_result={str(uid): {"status": "DatasetPipelineCompleted"}})
    client = _make_client(transport)
    asyncio.run(client.cognify(dataset_ids=[uid]))
    assert transport.json_calls[0][0] == "/api/v1/cognify"
    payload = transport.json_calls[0][1]
    assert payload["datasetIds"] == [str(uid)]
    assert payload["runInBackground"] is False


def test_ping_happy_path_returns_ok() -> None:
    uid = UUID("55555555-5555-5555-5555-555555555555")
    transport = _FakeTransport(
        multipart_result={
            "status": "DatasetCreated",
            "dataset_id": str(uid),
            "pipeline_run_id": "66666666-6666-6666-6666-666666666666",
            "dataset_name": "agnes_smoke",
        },
        json_result={str(uid): {"status": "ok"}},
    )
    client = _make_client(transport)
    result = asyncio.run(client.ping())
    assert result["ok"] is True
    assert result["dataset_id"] == str(uid)
    assert result["dataset"].endswith("_smoke")
    assert isinstance(result["latency_ms"], int)


def test_ping_surfaces_transport_error() -> None:
    err_transport = AsyncMock()
    err_transport.post_multipart.side_effect = CognneCloudError("/api/v1/add", 500, "boom")
    err_transport.post_json = AsyncMock()
    client = _make_client(err_transport)
    result = asyncio.run(client.ping())
    assert result["ok"] is False
    assert result["status"] == 500


def test_http_transport_resolves_headers() -> None:
    t = HttpTransport("https://example.test", "k-abc")
    assert t._headers(json_body=True) == {
        "X-Api-Key": "k-abc",
        "Content-Type": "application/json",
    }
    assert t._headers(json_body=False) == {"X-Api-Key": "k-abc"}
