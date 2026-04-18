"""Offline tests for the USITC DataWeb ingredient-price adapter."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from agnes.tools.usitc_dataweb import (
    PRICE_SCHEMA_VERSION,
    CountryBreakdown,
    ImportPriceSnapshot,
    PriceCache,
    USITCDataWebClient,
    USITCDataWebError,
    _build_payload,
    _coerce_number,
    _parse_snapshot,
    _safe_unit_value,
)

# ---------------------------------------------------------------------------
# pure helpers
# ---------------------------------------------------------------------------


def test_build_payload_minimal_shape() -> None:
    payload = _build_payload("293626", "2023", "Import")
    assert payload["tradeType"] == "Import"
    assert payload["classificationSystem"] == "HTS"
    assert payload["years"] == ["2023"]
    assert payload["commodities"] == ["293626"]
    assert "CUSTOMS_VALUE" in payload["dataToReport"]
    assert "PRIMARY_UNIT_OF_QUANTITY" in payload["dataToReport"]


def test_build_payload_coerces_year_to_string() -> None:
    payload = _build_payload("293626", 2024, "Import")  # type: ignore[arg-type]
    assert payload["years"] == ["2024"]


def test_coerce_number_handles_string_with_commas() -> None:
    assert _coerce_number("12,345.67") == pytest.approx(12345.67)
    assert _coerce_number(42) == 42.0
    assert _coerce_number("") is None
    assert _coerce_number("n/a") is None
    assert _coerce_number(None) is None
    assert _coerce_number("not a number") is None


def test_safe_unit_value_divides_only_when_positive() -> None:
    assert _safe_unit_value(100.0, 4.0) == 25.0
    assert _safe_unit_value(100.0, 0.0) is None
    assert _safe_unit_value(None, 4.0) is None
    assert _safe_unit_value(100.0, None) is None


# ---------------------------------------------------------------------------
# response parsing
# ---------------------------------------------------------------------------


def _sample_response() -> dict[str, Any]:
    return {
        "dto": {
            "tables": [
                {
                    "row_groups": [
                        {
                            "rowsNew": [
                                {
                                    "country": "Germany",
                                    "customsValue": "1,000,000",
                                    "firstUnitOfQuantity": "5000",
                                    "unitOfQuantity": "kg",
                                },
                                {
                                    "country": "China",
                                    "customsValue": 500_000,
                                    "firstUnitOfQuantity": 2_500,
                                },
                                {
                                    "country": "Total",
                                    "customsValue": 1_500_000,
                                    "firstUnitOfQuantity": 7_500,
                                },
                            ]
                        }
                    ]
                }
            ]
        }
    }


def test_parse_snapshot_aggregates_and_skips_total_row() -> None:
    snap = _parse_snapshot(
        _sample_response(), hts_code="293626", year="2023", trade_type="Import"
    )
    assert snap.hts_code == "293626"
    assert snap.year == "2023"
    assert snap.trade_type == "Import"
    assert snap.customs_value_usd == pytest.approx(3_000_000.0)
    assert snap.quantity == pytest.approx(15_000.0)
    assert snap.unit_value_usd == pytest.approx(200.0)
    assert snap.uom == "kg"
    countries = {c.country for c in snap.country_breakdown}
    assert countries == {"Germany", "China"}
    assert snap.schema_version == PRICE_SCHEMA_VERSION


def test_parse_snapshot_handles_empty_body() -> None:
    snap = _parse_snapshot({}, hts_code="999999", year="2023", trade_type="Import")
    assert snap.customs_value_usd is None
    assert snap.quantity is None
    assert snap.unit_value_usd is None
    assert snap.country_breakdown == []


def test_parse_snapshot_tolerates_alternate_field_names() -> None:
    alt = {
        "dto": {
            "tables": [
                {
                    "rowGroups": [
                        {
                            "rows": [
                                {
                                    "rt3Value": "Mexico",
                                    "CUSTOMS_VALUE": 200,
                                    "PRIMARY_UNIT_OF_QUANTITY": 10,
                                    "uom": "kg",
                                }
                            ]
                        }
                    ]
                }
            ]
        }
    }
    snap = _parse_snapshot(alt, hts_code="x", year="2023", trade_type="Import")
    assert snap.customs_value_usd == 200.0
    assert snap.quantity == 10.0
    assert snap.unit_value_usd == 20.0
    assert snap.country_breakdown[0].country == "Mexico"


# ---------------------------------------------------------------------------
# cache
# ---------------------------------------------------------------------------


def test_cache_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "prices.json"
    cache = PriceCache(path)
    snap = ImportPriceSnapshot(
        hts_code="293626",
        year="2023",
        trade_type="Import",
        customs_value_usd=1.0,
        quantity=2.0,
        unit_value_usd=0.5,
        uom="kg",
        country_breakdown=[
            CountryBreakdown(
                country="Germany",
                customs_value_usd=1.0,
                quantity=2.0,
                unit_value_usd=0.5,
            )
        ],
        fetched_at="2026-04-18T00:00:00+00:00",
    )
    from agnes.tools.usitc_dataweb import _CacheKey

    key = _CacheKey("293626", "2023", "Import")
    assert cache.get(key) is None
    cache.put(key, snap)

    # reopen to confirm disk persistence
    cache2 = PriceCache(path)
    loaded = cache2.get(key)
    assert loaded is not None
    assert loaded.customs_value_usd == 1.0
    assert loaded.country_breakdown[0].country == "Germany"


def test_cache_tolerates_corrupt_file(tmp_path: Path) -> None:
    path = tmp_path / "prices.json"
    path.write_text("not json")
    cache = PriceCache(path)  # must not raise
    from agnes.tools.usitc_dataweb import _CacheKey

    assert cache.get(_CacheKey("x", "y", "z")) is None


# ---------------------------------------------------------------------------
# client with stubbed transport
# ---------------------------------------------------------------------------


def _mock_transport(response: httpx.Response) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        # Make sure the adapter is sending Authorization + POST to runReport
        assert request.method == "POST"
        assert request.url.path.endswith("/api/v2/report2/runReport")
        assert request.headers["authorization"].startswith("Bearer ")
        body = json.loads(request.content.decode())
        assert body["tradeType"] == "Import"
        assert body["commodities"] == ["293626"]
        return response

    return httpx.MockTransport(handler)


def _make_client(
    transport: httpx.MockTransport,
    cache: PriceCache | None = None,
) -> USITCDataWebClient:
    http = httpx.Client(transport=transport, base_url="https://datawebws.usitc.gov/dataweb")
    return USITCDataWebClient(
        api_token="test-token",
        client=http,
        cache=cache,
    )


def test_client_requires_token() -> None:
    with pytest.raises(USITCDataWebError):
        USITCDataWebClient(api_token="")


def test_fetch_snapshot_happy_path(tmp_path: Path) -> None:
    resp = httpx.Response(200, json=_sample_response())
    transport = _mock_transport(resp)
    cache = PriceCache(tmp_path / "c.json")
    client = _make_client(transport, cache=cache)

    snap = client.fetch_snapshot(hts_code="293626", year="2023")
    assert snap.customs_value_usd == pytest.approx(3_000_000.0)
    assert snap.unit_value_usd == pytest.approx(200.0)

    # second call hits the cache (we close transport to prove it)
    client._client.close()
    snap2 = client.fetch_snapshot(hts_code="293626", year="2023")
    assert snap2 == snap


def test_fetch_snapshot_maintenance_503_raises() -> None:
    resp = httpx.Response(503, text="<html>maintenance</html>")
    transport = _mock_transport(resp)
    client = _make_client(transport)
    with pytest.raises(USITCDataWebError) as exc:
        client.fetch_snapshot(hts_code="293626", year="2023")
    assert "503" in str(exc.value) or "maintenance" in str(exc.value).lower()


def test_fetch_snapshot_401_token_rejected() -> None:
    resp = httpx.Response(401, text="expired")
    transport = _mock_transport(resp)
    client = _make_client(transport)
    with pytest.raises(USITCDataWebError) as exc:
        client.fetch_snapshot(hts_code="293626", year="2023")
    assert "401" in str(exc.value) or "token" in str(exc.value).lower()


def test_fetch_snapshot_non_json_body_raises() -> None:
    resp = httpx.Response(200, text="<!DOCTYPE html>oops")
    transport = _mock_transport(resp)
    client = _make_client(transport)
    with pytest.raises(USITCDataWebError):
        client.fetch_snapshot(hts_code="293626", year="2023")


def test_no_cache_flag_forces_refetch(tmp_path: Path) -> None:
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(200, json=_sample_response())

    transport = httpx.MockTransport(handler)
    cache = PriceCache(tmp_path / "c.json")
    client = _make_client(transport, cache=cache)

    client.fetch_snapshot(hts_code="293626", year="2023")
    client.fetch_snapshot(hts_code="293626", year="2023", use_cache=False)
    assert call_count["n"] == 2
