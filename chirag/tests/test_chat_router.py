"""Integration tests for the /api/chat router.

We never hit OpenAI — ``make_client`` is monkeypatched to return a stub whose
``chat.completions.create`` method yields a scripted sequence of tool-call and
final responses.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


class _Fn:
    def __init__(self, name: str, arguments: dict) -> None:
        self.name = name
        self.arguments = json.dumps(arguments)


class _ToolCall:
    def __init__(self, id_: str, name: str, args: dict) -> None:
        self.id = id_
        self.type = "function"
        self.function = _Fn(name, args)


class _Message:
    def __init__(self, content: str | None, tool_calls=None) -> None:
        self.content = content
        self.tool_calls = tool_calls


class _Choice:
    def __init__(self, msg: _Message) -> None:
        self.message = msg
        self.finish_reason = "stop"


class _Completion:
    def __init__(self, msg: _Message) -> None:
        self.choices = [_Choice(msg)]


class _ScriptedCompletions:
    def __init__(self, script: list[_Message]) -> None:
        self._script = list(script)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self._script:
            raise AssertionError("Ran out of scripted responses")
        msg = self._script.pop(0)
        return _Completion(msg)


class _ScriptedClient:
    def __init__(self, script: list[_Message]) -> None:
        self.chat = type("Chat", (), {})()
        self.chat.completions = _ScriptedCompletions(script)


@pytest.fixture
def chat_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Create a FastAPI app with a fake OpenAI client and empty reports dir."""

    monkeypatch.setenv("AGNES_OPENAI_API_KEY", "test-key-abc")
    monkeypatch.setenv("AGNES_REPORTS_DIR", str(tmp_path))

    db_path = tmp_path / "supply.sqlite"
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE Company (Id INTEGER PRIMARY KEY, Name TEXT);
        CREATE TABLE Product (
            Id INTEGER PRIMARY KEY, SKU TEXT, CompanyId INTEGER, Type TEXT
        );
        CREATE TABLE BOM (Id INTEGER PRIMARY KEY, ProducedProductId INTEGER);
        CREATE TABLE BOM_Component (BOMId INTEGER, ConsumedProductId INTEGER);
        CREATE TABLE Supplier (Id INTEGER PRIMARY KEY, Name TEXT);
        CREATE TABLE Supplier_Product (SupplierId INTEGER, ProductId INTEGER);
        INSERT INTO Company VALUES (1, 'Acme');
        """
    )
    conn.commit()
    conn.close()
    monkeypatch.setenv("AGNES_DB_PATH", str(db_path))

    return monkeypatch


def _build_client(
    monkeypatch: pytest.MonkeyPatch, script: list[_Message]
) -> tuple[TestClient, _ScriptedClient]:
    fake = _ScriptedClient(script)
    monkeypatch.setattr(
        "agnes.api.chat.make_client", lambda _k: fake, raising=True
    )
    from agnes.api.main import create_app

    app = create_app()
    client = TestClient(app)
    client.__enter__()
    return client, fake


def test_chat_happy_path_tool_then_final(chat_app: pytest.MonkeyPatch) -> None:
    script = [
        _Message(
            content=None,
            tool_calls=[
                _ToolCall(
                    "call_1",
                    "execute_sql",
                    {"query": "SELECT Id, Name FROM Company"},
                )
            ],
        ),
        _Message(content="Acme is the only company in the database."),
    ]
    client, fake = _build_client(chat_app, script)
    try:
        resp = client.post(
            "/api/chat",
            json={"message": "Which companies are in the database?"},
        )
    finally:
        client.__exit__(None, None, None)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["reply"] == "Acme is the only company in the database."
    assert body["finish_reason"] == "stop"
    assert body["schema_version"] == "v1"
    assert len(body["steps"]) == 1
    step = body["steps"][0]
    assert step["tool"] == "execute_sql"
    assert step["ok"] is True
    assert "Acme" in step["result_preview"]

    assert len(fake.chat.completions.calls) == 2
    second_call_msgs = fake.chat.completions.calls[1]["messages"]
    assert any(m["role"] == "tool" for m in second_call_msgs)


def test_chat_rejects_without_api_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AGNES_REPORTS_DIR", str(tmp_path))
    from agnes.api.main import create_app

    app = create_app()
    with TestClient(app) as c:
        c.app.state.settings.openai_api_key = None
        resp = c.post("/api/chat", json={"message": "hi"})
    assert resp.status_code == 503
    assert resp.json()["detail"]["error"] == "llm_unavailable"


def test_chat_surfaces_sql_guard_error_to_agent(
    chat_app: pytest.MonkeyPatch,
) -> None:
    script = [
        _Message(
            content=None,
            tool_calls=[
                _ToolCall(
                    "call_1",
                    "execute_sql",
                    {"query": "DROP TABLE Company"},
                )
            ],
        ),
        _Message(
            content="I can only run read-only SELECTs, so I cannot drop that table."
        ),
    ]
    client, _fake = _build_client(chat_app, script)
    try:
        resp = client.post(
            "/api/chat",
            json={"message": "Please drop the Company table"},
        )
    finally:
        client.__exit__(None, None, None)
    assert resp.status_code == 200
    body = resp.json()
    assert body["steps"][0]["ok"] is False
    assert body["steps"][0]["error"] == "only_select_queries_allowed"
    assert body["finish_reason"] == "stop"


def test_chat_max_iterations(chat_app: pytest.MonkeyPatch) -> None:
    def tool_msg() -> _Message:
        return _Message(
            content=None,
            tool_calls=[
                _ToolCall(
                    f"call_{id(object())}",
                    "execute_sql",
                    {"query": "SELECT 1"},
                )
            ],
        )

    script = [tool_msg() for _ in range(8)]
    client, _fake = _build_client(chat_app, script)
    try:
        resp = client.post("/api/chat", json={"message": "spin forever"})
    finally:
        client.__exit__(None, None, None)
    assert resp.status_code == 200
    body = resp.json()
    assert body["finish_reason"] == "max_iterations"
    assert len(body["steps"]) == 8
