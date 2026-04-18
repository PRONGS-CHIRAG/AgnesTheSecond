"""
Phase 7 structural sourcing signals.

Joins the canonical registry with the challenge DB's supplier tables to answer,
per ``(company_id, source_key, candidate_key)``:

* how many suppliers sell the source / candidate
* which suppliers overlap
* what fraction of the candidate's suppliers already serve this company
* whether adopting the candidate relieves single-source concentration

All functions are pure: they take pre-loaded frames / dicts so tests can stub
them without touching a real database.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
import structlog

from agnes.models.canonical import CanonicalRegistry
from agnes.models.recommendation import SourcingSignals

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class SupplierIndex:
    """Cached lookups derived from the registry + supplier tables."""

    suppliers_by_key: dict[str, set[int]]
    supplier_names_by_key: dict[str, list[str]]
    suppliers_by_company: dict[int, set[int]]
    raw_ids_by_key: dict[str, set[int]] = field(default_factory=dict)


def _raw_ids_by_key(registry: CanonicalRegistry) -> dict[str, set[int]]:
    out: dict[str, set[int]] = {}
    for mat in registry.materials:
        out.setdefault(mat.canonical_key, set()).add(mat.raw_product_id)
    return out


def build_supplier_index(
    registry: CanonicalRegistry,
    suppliers_df: pd.DataFrame,
    company_df: pd.DataFrame,
) -> SupplierIndex:
    """
    Build a :class:`SupplierIndex` from:

    * ``registry``: Phase 2 canonical registry (canonical_key -> raw ids).
    * ``suppliers_df``: :func:`agnes.data.queries.raw_material_suppliers` output.
      Expected columns: ``ProductId``, ``supplier_ids`` (list[int]),
      ``supplier_names`` (list[str]).
    * ``company_df``: :func:`agnes.data.queries.supplier_products_by_company`
      output. Expected columns: ``CompanyId``, ``SupplierId``.

    The resulting index supports cheap per-pair lookups.
    """
    raw_ids_by_key = _raw_ids_by_key(registry)

    per_raw_ids: dict[int, set[int]] = {}
    per_raw_names: dict[int, list[str]] = {}
    if not suppliers_df.empty:
        for _, row in suppliers_df.iterrows():
            raw_id = int(row["ProductId"])
            ids = list(row.get("supplier_ids") or [])
            names = list(row.get("supplier_names") or [])
            per_raw_ids[raw_id] = {int(x) for x in ids}
            per_raw_names[raw_id] = [str(x) for x in names]

    suppliers_by_key: dict[str, set[int]] = {}
    supplier_names_by_key: dict[str, list[str]] = {}
    for canonical_key, raw_ids in raw_ids_by_key.items():
        merged_ids: set[int] = set()
        merged_names: list[str] = []
        seen: set[str] = set()
        for rid in raw_ids:
            merged_ids.update(per_raw_ids.get(rid, set()))
            for name in per_raw_names.get(rid, []):
                if name not in seen:
                    seen.add(name)
                    merged_names.append(name)
        suppliers_by_key[canonical_key] = merged_ids
        supplier_names_by_key[canonical_key] = sorted(merged_names)

    suppliers_by_company: dict[int, set[int]] = {}
    if not company_df.empty:
        for _, row in company_df.iterrows():
            cid = int(row["CompanyId"])
            sid = int(row["SupplierId"])
            suppliers_by_company.setdefault(cid, set()).add(sid)

    logger.info(
        "phase7_supplier_index_built",
        n_keys=len(suppliers_by_key),
        n_companies=len(suppliers_by_company),
    )
    return SupplierIndex(
        suppliers_by_key=suppliers_by_key,
        supplier_names_by_key=supplier_names_by_key,
        suppliers_by_company=suppliers_by_company,
        raw_ids_by_key=raw_ids_by_key,
    )


def compute_signals(
    index: SupplierIndex,
    *,
    company_id: int,
    source_key: str,
    candidate_key: str,
) -> SourcingSignals:
    """
    Compute :class:`SourcingSignals` for one ``(company, source, candidate)`` triple.

    * ``concentration_relief`` = 1.0 iff ``source`` has <=1 supplier AND the
      candidate has >=2 suppliers (a credible alternative exists).
    * ``company_supplier_overlap`` = fraction of the candidate's suppliers that
      already serve this company for ANY raw material.
    * ``missing_signals`` surfaces ``"no_supplier_data"`` when either side has
      zero known suppliers, since downstream scoring then treats the benefit as
      neutral rather than punishing the candidate.
    """
    source_suppliers = index.suppliers_by_key.get(source_key, set())
    candidate_suppliers = index.suppliers_by_key.get(candidate_key, set())
    company_suppliers = index.suppliers_by_company.get(company_id, set())

    shared = sorted(source_suppliers & candidate_suppliers)
    source_count = len(source_suppliers)
    candidate_count = len(candidate_suppliers)

    if candidate_count > 0:
        overlap_ids = candidate_suppliers & company_suppliers
        overlap = len(overlap_ids) / candidate_count
    else:
        overlap = 0.0

    concentration_relief = (
        1.0 if (source_count <= 1 and candidate_count >= 2) else 0.0
    )

    missing: list[str] = []
    if source_count == 0 or candidate_count == 0:
        missing.append("no_supplier_data")

    return SourcingSignals(
        source_supplier_count=source_count,
        candidate_supplier_count=candidate_count,
        shared_supplier_ids=shared,
        company_supplier_overlap=round(overlap, 4),
        concentration_relief=concentration_relief,
        missing_signals=missing,
    )
