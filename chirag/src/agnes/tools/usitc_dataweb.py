"""USITC DataWeb adapter for ingredient import prices.

DataWeb is the US International Trade Commission's trade-statistics API
(https://datawebws.usitc.gov/dataweb). It exposes aggregate US imports and
exports by HTS commodity code, country, and period. From a trade-value +
quantity pair we derive a **unit value** (USD per unit), which Agnes treats
as a demand-side proxy for ingredient market price.

Design:
- One adapter class; synchronous httpx under the hood (the rest of the
  tooling uses sync httpx, e.g. ``tools/web_search.py``).
- Bearer JWT from ``settings.usitc_api_token``; missing token short-circuits
  with a typed ``USITCDataWebError`` instead of a live 401.
- Response parsing is defensive: DataWeb returns a deeply nested DTO whose
  exact shape is not contractually pinned, so we walk the tree with
  ``.get()`` and fall back to ``None`` for any missing field rather than
  raising.
- On-disk JSON cache keyed by ``(hts_code, year, trade_type)`` so reruns
  are idempotent and free.
- Every non-2xx response (including the frequent maintenance-window 503
  HTML page) raises ``USITCDataWebError`` with a truncated body so the
  CLI can log a useful message without leaking a 50 KB HTML blob.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import structlog
from pydantic import BaseModel, ConfigDict, Field

logger = structlog.get_logger(__name__)


PRICE_SCHEMA_VERSION = "v1"
RUN_REPORT_PATH = "/api/v2/report2/runReport"


class USITCDataWebError(RuntimeError):
    """Raised when the DataWeb adapter cannot produce a usable response."""


class CountryBreakdown(BaseModel):
    """Per-country aggregate row within a price snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    country: str
    customs_value_usd: float | None = None
    quantity: float | None = None
    unit_value_usd: float | None = None


class ImportPriceSnapshot(BaseModel):
    """One ``(hts_code, year, trade_type)`` unit-value reading."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    hts_code: str = Field(description="HTS commodity code as queried (6/8/10 digits).")
    year: str
    trade_type: str = Field(description="Usually 'Import'.")
    customs_value_usd: float | None = Field(
        default=None, description="Sum of customs (cost + freight) value across countries."
    )
    quantity: float | None = Field(
        default=None, description="First unit of quantity (units vary by HTS; see uom)."
    )
    unit_value_usd: float | None = Field(
        default=None, description="customs_value_usd / quantity, None if either missing."
    )
    uom: str | None = Field(
        default=None, description="Unit-of-measure label reported by DataWeb (e.g. 'kg')."
    )
    country_breakdown: list[CountryBreakdown] = Field(default_factory=list)
    fetched_at: str = Field(description="UTC ISO timestamp at fetch time.")
    schema_version: str = Field(default=PRICE_SCHEMA_VERSION)


@dataclass(frozen=True)
class _CacheKey:
    hts_code: str
    year: str
    trade_type: str

    def to_str(self) -> str:
        return f"{self.hts_code}|{self.year}|{self.trade_type}|{PRICE_SCHEMA_VERSION}"


class PriceCache:
    """Disk-backed JSON cache for ``ImportPriceSnapshot`` rows.

    Keys embed :data:`PRICE_SCHEMA_VERSION` so future response-shape changes
    miss cleanly without manual eviction.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._data: dict[str, dict[str, Any]] = {}
        if path.exists():
            try:
                self._data = json.loads(path.read_text())
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("usitc_cache_load_failed", path=str(path), err=str(exc)[:200])
                self._data = {}

    def get(self, key: _CacheKey) -> ImportPriceSnapshot | None:
        raw = self._data.get(key.to_str())
        if raw is None:
            return None
        try:
            return ImportPriceSnapshot.model_validate(raw)
        except ValueError:
            return None

    def put(self, key: _CacheKey, snapshot: ImportPriceSnapshot) -> None:
        self._data[key.to_str()] = snapshot.model_dump()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._data, indent=2, sort_keys=True))


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _truncate(text: str, n: int = 500) -> str:
    return text if len(text) <= n else text[:n] + "...(truncated)"


def _build_payload(hts_code: str, year: str, trade_type: str) -> dict[str, Any]:
    """Compose a minimal DataWeb runReport body for a single HTS + year.

    Keeping this pure makes it trivial to snapshot-test payload stability.
    """
    return {
        "tradeType": trade_type,
        "classificationSystem": "HTS",
        "dataToReport": ["CUSTOMS_VALUE", "PRIMARY_UNIT_OF_QUANTITY"],
        "timeframeSelectType": "fullYears",
        "years": [str(year)],
        "commodities": [hts_code],
        "commoditySelectType": "commodities",
        "countriesSelectType": "all",
        "countriesAgg": "DIS",
        "commoditiesAgg": "AGG",
    }


def _coerce_number(raw: Any) -> float | None:
    """DataWeb often ships numbers as strings with commas; be lenient."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        cleaned = raw.replace(",", "").strip()
        if not cleaned or cleaned.lower() in {"n/a", "na", "-"}:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _safe_unit_value(customs: float | None, qty: float | None) -> float | None:
    if customs is None or qty is None or qty <= 0:
        return None
    return customs / qty


def _walk_rows(response: dict[str, Any]) -> Iterable[dict[str, Any]]:
    """Yield row dicts from the DataWeb DTO tree, tolerating shape drift."""
    dto = response.get("dto") if isinstance(response, dict) else None
    if not isinstance(dto, dict):
        return
    tables = dto.get("tables") or []
    if not isinstance(tables, list):
        return
    for table in tables:
        if not isinstance(table, dict):
            continue
        groups = table.get("row_groups") or table.get("rowGroups") or []
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            rows = group.get("rowsNew") or group.get("rows") or []
            if not isinstance(rows, list):
                continue
            for row in rows:
                if isinstance(row, dict):
                    yield row


def _parse_snapshot(
    response: dict[str, Any], *, hts_code: str, year: str, trade_type: str
) -> ImportPriceSnapshot:
    """Parse a runReport response into an :class:`ImportPriceSnapshot`.

    Walks ``dto.tables[*].row_groups[*].rowsNew`` and aggregates the per-row
    customs value + quantity. When country-level rows are present they are
    preserved as a breakdown; a single aggregated row still yields a valid
    snapshot with an empty ``country_breakdown``.
    """
    total_customs = 0.0
    total_qty = 0.0
    customs_seen = False
    qty_seen = False
    uom: str | None = None
    breakdown: list[CountryBreakdown] = []

    for row in _walk_rows(response):
        country = str(row.get("country") or row.get("rt3Value") or row.get("label") or "").strip()
        customs = _coerce_number(
            row.get("customsValue")
            or row.get("CUSTOMS_VALUE")
            or row.get("customs_value")
        )
        qty = _coerce_number(
            row.get("firstUnitOfQuantity")
            or row.get("PRIMARY_UNIT_OF_QUANTITY")
            or row.get("quantity")
            or row.get("first_unit_of_quantity")
        )
        uom = uom or str(row.get("unitOfQuantity") or row.get("uom") or "") or None

        if customs is not None:
            total_customs += customs
            customs_seen = True
        if qty is not None:
            total_qty += qty
            qty_seen = True

        if country and country.lower() not in {"total", "world"}:
            breakdown.append(
                CountryBreakdown(
                    country=country,
                    customs_value_usd=customs,
                    quantity=qty,
                    unit_value_usd=_safe_unit_value(customs, qty),
                )
            )

    customs_sum = total_customs if customs_seen else None
    qty_sum = total_qty if qty_seen else None

    return ImportPriceSnapshot(
        hts_code=hts_code,
        year=str(year),
        trade_type=trade_type,
        customs_value_usd=customs_sum,
        quantity=qty_sum,
        unit_value_usd=_safe_unit_value(customs_sum, qty_sum),
        uom=uom or None,
        country_breakdown=breakdown,
        fetched_at=_now_iso(),
    )


class USITCDataWebClient:
    """Thin, synchronous client over the DataWeb runReport endpoint.

    Not thread-safe. The underlying ``httpx.Client`` is created lazily and
    closed via :meth:`close` (or via the context-manager protocol).
    """

    def __init__(
        self,
        *,
        api_token: str | None,
        base_url: str = "https://datawebws.usitc.gov/dataweb",
        timeout_seconds: float = 60.0,
        client: httpx.Client | None = None,
        cache: PriceCache | None = None,
        clock: callable[[], float] | None = None,
    ) -> None:
        if not api_token:
            raise USITCDataWebError(
                "USITC DataWeb token is required (set AGNES_USITC_API_TOKEN)"
            )
        self._token = api_token
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._client = client or httpx.Client(timeout=timeout_seconds)
        self._cache = cache
        self._clock = clock or time.monotonic

    def __enter__(self) -> USITCDataWebClient:
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:  # pragma: no cover - defensive
            pass

    def fetch_snapshot(
        self,
        *,
        hts_code: str,
        year: str,
        trade_type: str = "Import",
        use_cache: bool = True,
    ) -> ImportPriceSnapshot:
        """Return one ``(hts_code, year, trade_type)`` price snapshot.

        Caches on success; a cache miss plus any HTTP/transport error surfaces
        as :class:`USITCDataWebError` so the caller can degrade gracefully.
        """
        key = _CacheKey(hts_code=hts_code, year=str(year), trade_type=trade_type)
        if use_cache and self._cache is not None:
            cached = self._cache.get(key)
            if cached is not None:
                logger.info(
                    "usitc_cache_hit",
                    hts=hts_code,
                    year=year,
                    trade_type=trade_type,
                )
                return cached

        payload = _build_payload(hts_code, str(year), trade_type)
        url = f"{self._base_url}{RUN_REPORT_PATH}"
        started = self._clock()
        try:
            resp = self._client.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
        except httpx.HTTPError as exc:
            logger.exception(
                "usitc_transport_error", hts=hts_code, year=year, err=str(exc)[:200]
            )
            raise USITCDataWebError(f"DataWeb transport error: {exc}") from exc

        latency_ms = int((self._clock() - started) * 1000)

        if resp.status_code == 401:
            raise USITCDataWebError(
                "DataWeb rejected the token (401). Check AGNES_USITC_API_TOKEN."
            )
        if resp.status_code == 429:
            raise USITCDataWebError(
                f"DataWeb rate-limited (429): {_truncate(resp.text)}"
            )
        if resp.status_code == 503:
            raise USITCDataWebError(
                "DataWeb is under maintenance (503). Retry later."
            )
        if resp.status_code >= 400:
            raise USITCDataWebError(
                f"DataWeb http {resp.status_code}: {_truncate(resp.text)}"
            )

        try:
            data = resp.json()
        except ValueError as exc:
            raise USITCDataWebError(
                f"DataWeb returned non-JSON body: {_truncate(resp.text)}"
            ) from exc

        snapshot = _parse_snapshot(
            data, hts_code=hts_code, year=str(year), trade_type=trade_type
        )

        logger.info(
            "usitc_fetch_ok",
            hts=hts_code,
            year=year,
            trade_type=trade_type,
            customs_value_usd=snapshot.customs_value_usd,
            quantity=snapshot.quantity,
            countries=len(snapshot.country_breakdown),
            latency_ms=latency_ms,
        )

        if use_cache and self._cache is not None:
            self._cache.put(key, snapshot)
        return snapshot
