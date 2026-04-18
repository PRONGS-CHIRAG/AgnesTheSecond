"""Smoke tests for the FastAPI artifact endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agnes.api.main import create_app

REPORTS = Path("outputs/reports")


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    with TestClient(app) as c:
        yield c


def test_health(client: TestClient) -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_summary_artifacts_block(client: TestClient) -> None:
    resp = client.get("/api/summary")
    assert resp.status_code == 200
    body = resp.json()
    names = [a["name"] for a in body["artifacts"]]
    assert names == [
        "registry",
        "candidates",
        "evidence",
        "assessments",
        "recommendations",
    ]


@pytest.mark.skipif(
    not (REPORTS / "canonical_registry.json").is_file(),
    reason="Phase 2 registry artifact not present",
)
def test_registry_paged(client: TestClient) -> None:
    resp = client.get("/api/registry", params={"limit": 5, "offset": 0})
    assert resp.status_code == 200
    body = resp.json()
    assert body["limit"] == 5
    assert body["offset"] == 0
    assert isinstance(body["items"], list)
    assert len(body["items"]) <= 5
    assert isinstance(body["families"], list)
    assert isinstance(body["roles"], list)


@pytest.mark.skipif(
    not (REPORTS / "canonical_registry.json").is_file(),
    reason="Phase 2 registry artifact not present",
)
def test_registry_filter_by_family_or_role(client: TestClient) -> None:
    base = client.get("/api/registry", params={"limit": 500}).json()
    if not base["families"]:
        pytest.skip("no families in registry")
    fam = base["families"][0]
    resp = client.get("/api/registry", params={"family": fam, "limit": 500})
    assert resp.status_code == 200
    items = resp.json()["items"]
    for item in items:
        assert item["ingredient_family"] == fam


@pytest.mark.skipif(
    not (REPORTS / "substitute_candidates.json").is_file(),
    reason="Phase 4 candidates artifact not present",
)
def test_candidates_endpoint(client: TestClient) -> None:
    resp = client.get("/api/candidates")
    assert resp.status_code == 200
    body = resp.json()
    assert "candidates" in body
    assert "schema_version" in body


@pytest.mark.skipif(
    not (REPORTS / "substitute_evidence.json").is_file(),
    reason="Phase 5 evidence artifact not present",
)
def test_evidence_pair_roundtrip(client: TestClient) -> None:
    report = client.get("/api/evidence").json()
    if not report["items"]:
        pytest.skip("no evidence items")
    first = report["items"][0]
    resp = client.get(
        f"/api/evidence/{first['source_key']}/{first['candidate_key']}"
    )
    assert resp.status_code == 200
    assert resp.json()["source_key"] == first["source_key"]


def test_evidence_pair_missing(client: TestClient) -> None:
    resp = client.get(
        "/api/evidence/definitely-not-a-source/definitely-not-a-candidate"
    )
    # Either the file is missing (404 artifact_missing) or the pair is missing.
    assert resp.status_code == 404
    detail = resp.json()["detail"]
    assert detail["error"] in {"artifact_missing", "evidence_pair_not_found"}


def test_dashboard_bundle_shape(client: TestClient) -> None:
    resp = client.get("/api/dashboard")
    assert resp.status_code == 200
    body = resp.json()
    for key in (
        "summary",
        "registry",
        "candidates",
        "evidence",
        "assessments",
        "recommendations",
        "opportunity_details",
        "missing",
    ):
        assert key in body, f"missing key {key}"

    # summary block always present and well-formed
    assert isinstance(body["summary"]["artifacts"], list)
    assert isinstance(body["missing"], list)
    assert isinstance(body["opportunity_details"], list)

    # registry aggregates only check when the registry was loaded
    if body["registry"] is not None:
        reg = body["registry"]
        assert reg["total"] == len(reg["items"])
        assert sum(reg["family_counts"].values()) == reg["total"]
        assert sum(reg["role_counts"].values()) == reg["total"]
        assert sum(b["n"] for b in reg["confidence_histogram"]) == reg["total"]
        assert set(reg["families"]) == set(reg["family_counts"].keys())
        assert set(reg["roles"]) == set(reg["role_counts"].keys())

    # every pre-joined opportunity detail should match a known opportunity
    if body["recommendations"] is not None:
        opp_keys = {o["source_key"] for o in body["recommendations"]["opportunities"]}
        for det in body["opportunity_details"]:
            assert det["opportunity"]["source_key"] in opp_keys
            # rows are always a subset of the opportunity's source_key
            for r in det["rows"]:
                assert r["source_key"] == det["opportunity"]["source_key"]


@pytest.mark.skipif(
    not (REPORTS / "sourcing_recommendations.json").is_file(),
    reason="Phase 7 recommendations artifact not present",
)
def test_opportunity_detail(client: TestClient) -> None:
    opps = client.get("/api/opportunities").json()
    if not opps:
        pytest.skip("no opportunities")
    src = opps[0]["source_key"]
    resp = client.get(f"/api/opportunities/{src}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["opportunity"]["source_key"] == src
    assert isinstance(body["rows"], list)
    assert isinstance(body["evidence"], list)
    assert isinstance(body["assessments"], list)
    assert isinstance(body["candidates"], list)
