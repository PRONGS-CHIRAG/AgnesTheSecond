"""Run manager + SSE smoke tests using a stub phase script."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agnes.api.main import create_app
from agnes.api.services.run_manager import _PHASE_SCRIPTS


@pytest.fixture
def stub_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Build a throwaway repo root where phase4 is replaced with a tiny script."""
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    stub = scripts_dir / "stub_phase.py"
    stub.write_text(
        "import sys, time\n"
        "sys.stdout.write('hello line 1\\n')\n"
        "sys.stdout.flush()\n"
        "time.sleep(0.05)\n"
        "sys.stdout.write('hello line 2\\n')\n"
        "sys.stdout.flush()\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )
    reports = tmp_path / "outputs" / "reports"
    reports.mkdir(parents=True)

    # Point the API at the throwaway repo and rewire phase4 to the stub script.
    monkeypatch.setenv("AGNES_REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("AGNES_REPORTS_DIR", str(reports))
    original = _PHASE_SCRIPTS["phase4"]
    _PHASE_SCRIPTS["phase4"] = "scripts/stub_phase.py"
    try:
        yield tmp_path
    finally:
        _PHASE_SCRIPTS["phase4"] = original


@pytest.fixture
def client(stub_project: Path) -> TestClient:
    app = create_app()
    with TestClient(app) as c:
        yield c


def test_run_lifecycle_and_snapshot(client: TestClient) -> None:
    resp = client.post("/api/runs/phase4", json={})
    assert resp.status_code == 200, resp.text
    run_id = resp.json()["run_id"]
    assert resp.json()["phase"] == "phase4"

    # poll until the run finishes (stub is fast)
    deadline = time.time() + 10
    final = None
    while time.time() < deadline:
        snap = client.get(f"/api/runs/{run_id}").json()
        if snap["status"] in {"succeeded", "failed", "cancelled"}:
            final = snap
            break
        time.sleep(0.05)

    assert final is not None, "run never terminated"
    assert final["status"] == "succeeded", final
    assert final["exit_code"] == 0
    assert any("hello line 1" in log["text"] for log in final["logs"])


def test_runs_list_returns_recent(client: TestClient) -> None:
    client.post("/api/runs/phase4", json={})
    # let it finish to avoid tripping the one-per-phase guard
    time.sleep(0.5)
    body = client.get("/api/runs").json()
    assert isinstance(body["runs"], list)
    assert body["runs"], "expected at least one run in history"


def test_unknown_run_snapshot_404(client: TestClient) -> None:
    resp = client.get("/api/runs/does-not-exist")
    assert resp.status_code == 404


def test_cancel_unknown_409(client: TestClient) -> None:
    resp = client.post("/api/runs/does-not-exist/cancel")
    assert resp.status_code == 409


def test_concurrent_run_conflict(stub_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Spawn a slow stub and verify the second POST returns 409."""
    slow = stub_project / "scripts" / "stub_slow.py"
    slow.write_text(
        "import time, sys\n"
        "for i in range(50):\n"
        "    sys.stdout.write(f'tick {i}\\n'); sys.stdout.flush(); time.sleep(0.1)\n",
        encoding="utf-8",
    )
    original = _PHASE_SCRIPTS["phase4"]
    _PHASE_SCRIPTS["phase4"] = "scripts/stub_slow.py"
    app = create_app()
    try:
        with TestClient(app) as client:
            first = client.post("/api/runs/phase4", json={})
            assert first.status_code == 200
            run_id = first.json()["run_id"]

            second = client.post("/api/runs/phase4", json={})
            assert second.status_code == 409
            assert second.json()["detail"]["error"] == "run_conflict"

            cancel = client.post(f"/api/runs/{run_id}/cancel")
            assert cancel.status_code == 200

            # allow the cancel to propagate
            deadline = time.time() + 5
            while time.time() < deadline:
                snap = client.get(f"/api/runs/{run_id}").json()
                if snap["status"] in {"cancelled", "failed", "succeeded"}:
                    break
                time.sleep(0.05)
    finally:
        _PHASE_SCRIPTS["phase4"] = original
        os.environ.pop("AGNES_REPO_ROOT", None)
        os.environ.pop("AGNES_REPORTS_DIR", None)
