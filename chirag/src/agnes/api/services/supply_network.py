"""Memoized supply-network bundle service.

Builds ``SupplyNetworkBundle`` from the SQLite DB + the Phase 2 canonical
registry, cached by ``(db_path, db_mtime_ns, registry_mtime_ns)`` so any DB
file swap or registry re-run invalidates the in-memory payload.
"""

from __future__ import annotations

import threading
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime

from agnes.api.services.artifact_loader import ArtifactLoader, ArtifactMissingError
from agnes.config.settings import Settings
from agnes.data.db_loader import get_engine
from agnes.data.queries import (
    company_product_tree,
    load_companies,
    load_products,
    load_supplier_products,
    load_suppliers,
    supplier_products_by_company,
)
from agnes.models.canonical import CanonicalMaterial
from agnes.models.supply_network import (
    CompanyNode,
    CompanySupplierEdge,
    ProductNode,
    ProductRawEdge,
    SupplierNode,
    SupplierProductEdge,
    SupplierRawEdge,
    SupplyNetworkAggregates,
    SupplyNetworkBundle,
)


@dataclass(frozen=True)
class _CacheKey:
    db_path: str
    db_mtime_ns: int
    registry_mtime_ns: int | None


@dataclass
class _Cache:
    key: _CacheKey
    bundle: SupplyNetworkBundle


class SupplyNetworkService:
    """Compose DB + registry into a single ``SupplyNetworkBundle``."""

    def __init__(self, settings: Settings, loader: ArtifactLoader) -> None:
        self._settings = settings
        self._loader = loader
        self._lock = threading.Lock()
        self._cache: _Cache | None = None

    def get(self) -> SupplyNetworkBundle:
        """Return a fresh bundle, reusing cache when inputs are unchanged."""
        db_path = self._settings.db_path.resolve()
        if not db_path.is_file():
            raise FileNotFoundError(f"Database file not found: {db_path}")
        db_mtime_ns = db_path.stat().st_mtime_ns

        registry_status = self._loader.status("registry")
        registry_mtime_ns = registry_status.mtime_ns if registry_status.present else None

        key = _CacheKey(
            db_path=str(db_path),
            db_mtime_ns=db_mtime_ns,
            registry_mtime_ns=registry_mtime_ns,
        )
        with self._lock:
            if self._cache is not None and self._cache.key == key:
                return self._cache.bundle

        bundle = self._build()

        with self._lock:
            self._cache = _Cache(key=key, bundle=bundle)
        return bundle

    def invalidate(self) -> None:
        with self._lock:
            self._cache = None

    # ------------------------------------------------------------------

    def _build(self) -> SupplyNetworkBundle:
        engine = get_engine(self._settings)

        companies_df = load_companies(engine)
        products_df = load_products(engine)
        suppliers_df = load_suppliers(engine)
        supplier_products_df = load_supplier_products(engine)
        tree_df = company_product_tree(engine)
        sp_by_company_df = supplier_products_by_company(engine)

        try:
            registry = self._loader.get_registry()
            canonical_by_raw_id: dict[int, CanonicalMaterial] = {
                m.raw_product_id: m for m in registry.materials
            }
        except ArtifactMissingError:
            canonical_by_raw_id = {}

        company_by_id = {
            int(row.Id): str(row.Name) for row in companies_df.itertuples(index=False)
        }
        supplier_by_id = {
            int(row.Id): str(row.Name) for row in suppliers_df.itertuples(index=False)
        }
        product_by_id: dict[int, tuple[str, int, str]] = {
            int(row.Id): (str(row.SKU), int(row.CompanyId), str(row.Type))
            for row in products_df.itertuples(index=False)
        }

        supplier_rows = [
            (int(r.SupplierId), int(r.ProductId))
            for r in supplier_products_df.itertuples(index=False)
        ]

        # Per raw-product supplier count (for sole-source detection)
        suppliers_per_raw: Counter[int] = Counter()
        for _sid, pid in supplier_rows:
            suppliers_per_raw[pid] += 1

        raw_product_ids = {
            pid for pid, (_sku, _cid, ptype) in product_by_id.items() if ptype == "raw-material"
        }
        finished_product_ids = {
            pid for pid, (_sku, _cid, ptype) in product_by_id.items() if ptype == "finished-good"
        }
        sole_source_raw_ids = sorted(
            pid for pid in raw_product_ids if suppliers_per_raw.get(pid, 0) == 1
        )
        sole_source_raw_ids_set = set(sole_source_raw_ids)

        # BOM counts per finished good + supplier counts per raw (from tree_df for stability)
        bom_count_by_fg: Counter[int] = Counter()
        for r in tree_df.itertuples(index=False):
            bom_count_by_fg[int(r.FinishedProductId)] += 1

        # Supplier-level aggregations
        supplier_products: dict[int, set[int]] = {}
        supplier_canonical_keys: dict[int, set[str]] = {}
        supplier_companies: dict[int, set[int]] = {}
        supplier_family_counts: dict[int, Counter[str]] = {}
        supplier_sole_source: dict[int, int] = {}

        for sid, pid in supplier_rows:
            supplier_products.setdefault(sid, set()).add(pid)
            mat = canonical_by_raw_id.get(pid)
            if mat is not None:
                supplier_canonical_keys.setdefault(sid, set()).add(mat.canonical_key)
                supplier_family_counts.setdefault(sid, Counter())[mat.ingredient_family] += 1
            if pid in sole_source_raw_ids_set:
                supplier_sole_source[sid] = supplier_sole_source.get(sid, 0) + 1

        for r in sp_by_company_df.itertuples(index=False):
            sid = int(r.SupplierId)
            cid = int(r.CompanyId)
            supplier_companies.setdefault(sid, set()).add(cid)

        suppliers: list[SupplierNode] = []
        for sid, name in sorted(supplier_by_id.items(), key=lambda kv: kv[0]):
            fam_counter = supplier_family_counts.get(sid, Counter())
            top_families = [fam for fam, _ in fam_counter.most_common(3)]
            suppliers.append(
                SupplierNode(
                    id=sid,
                    name=name,
                    product_count=len(supplier_products.get(sid, ())),
                    canonical_key_count=len(supplier_canonical_keys.get(sid, ())),
                    company_count=len(supplier_companies.get(sid, ())),
                    sole_source_count=supplier_sole_source.get(sid, 0),
                    top_families=top_families,
                )
            )

        # Company-level aggregations
        company_fg_counts: Counter[int] = Counter()
        company_raw_counts: Counter[int] = Counter()
        for _pid, (_sku, cid, ptype) in product_by_id.items():
            if ptype == "finished-good":
                company_fg_counts[cid] += 1
            elif ptype == "raw-material":
                company_raw_counts[cid] += 1
        company_suppliers: dict[int, set[int]] = {}
        for r in sp_by_company_df.itertuples(index=False):
            company_suppliers.setdefault(int(r.CompanyId), set()).add(int(r.SupplierId))

        companies: list[CompanyNode] = []
        for cid, name in sorted(company_by_id.items(), key=lambda kv: kv[0]):
            companies.append(
                CompanyNode(
                    id=cid,
                    name=name,
                    finished_good_count=company_fg_counts.get(cid, 0),
                    raw_material_count=company_raw_counts.get(cid, 0),
                    supplier_count=len(company_suppliers.get(cid, ())),
                )
            )

        # Product nodes (all 1025 rows)
        products: list[ProductNode] = []
        for pid, (sku, cid, ptype) in sorted(product_by_id.items(), key=lambda kv: kv[0]):
            mat = canonical_by_raw_id.get(pid) if ptype == "raw-material" else None
            products.append(
                ProductNode(
                    id=pid,
                    sku=sku,
                    company_id=cid,
                    company_name=company_by_id.get(cid, ""),
                    type=ptype,  # type: ignore[arg-type]
                    normalized_name=mat.normalized_name if mat else None,
                    canonical_key=mat.canonical_key if mat else None,
                    ingredient_family=mat.ingredient_family if mat else None,
                    functional_role=mat.functional_role if mat else None,
                    confidence=float(mat.confidence) if mat else None,
                    supplier_count=(
                        int(suppliers_per_raw.get(pid, 0)) if ptype == "raw-material" else None
                    ),
                    bom_count=(
                        int(bom_count_by_fg.get(pid, 0)) if ptype == "finished-good" else None
                    ),
                )
            )

        # Edge lists
        product_company_cache = {
            pid: (sku, cid) for pid, (sku, cid, _t) in product_by_id.items()
        }

        supplier_product_edges: list[SupplierProductEdge] = []
        for sid, pid in sorted(supplier_rows):
            sku, cid = product_company_cache.get(pid, ("", -1))
            mat = canonical_by_raw_id.get(pid)
            supplier_product_edges.append(
                SupplierProductEdge(
                    supplier_id=sid,
                    supplier_name=supplier_by_id.get(sid, ""),
                    product_id=pid,
                    product_sku=sku,
                    company_id=cid,
                    company_name=company_by_id.get(cid, ""),
                    canonical_key=mat.canonical_key if mat else None,
                    ingredient_family=mat.ingredient_family if mat else None,
                    functional_role=mat.functional_role if mat else None,
                )
            )

        # Company <-> supplier edges: group by (company, supplier)
        cs_raws: dict[tuple[int, int], list[int]] = {}
        for r in sp_by_company_df.itertuples(index=False):
            key = (int(r.CompanyId), int(r.SupplierId))
            cs_raws.setdefault(key, []).append(int(r.RawProductId))

        company_supplier_edges: list[CompanySupplierEdge] = []
        for (cid, sid), raws in sorted(cs_raws.items()):
            ckeys = sorted(
                {
                    canonical_by_raw_id[r].canonical_key
                    for r in raws
                    if r in canonical_by_raw_id
                }
            )[:10]
            company_supplier_edges.append(
                CompanySupplierEdge(
                    company_id=cid,
                    company_name=company_by_id.get(cid, ""),
                    supplier_id=sid,
                    supplier_name=supplier_by_id.get(sid, ""),
                    shared_raw_count=len(raws),
                    canonical_keys=ckeys,
                )
            )

        # Product (finished) <-> raw edges from the BOM tree
        product_raw_edges: list[ProductRawEdge] = []
        for r in tree_df.itertuples(index=False):
            raw_id = int(r.RawProductId)
            mat = canonical_by_raw_id.get(raw_id)
            product_raw_edges.append(
                ProductRawEdge(
                    finished_product_id=int(r.FinishedProductId),
                    finished_sku=str(r.FinishedSKU),
                    company_id=int(r.CompanyId),
                    company_name=str(r.CompanyName),
                    raw_product_id=raw_id,
                    raw_sku=str(r.RawSKU),
                    canonical_key=mat.canonical_key if mat else None,
                    ingredient_family=mat.ingredient_family if mat else None,
                )
            )

        # Supplier <-> raw edges (subset with canonical_key present)
        supplier_raw_edges: list[SupplierRawEdge] = []
        for edge in supplier_product_edges:
            if edge.canonical_key is None:
                continue
            if edge.product_id not in raw_product_ids:
                continue
            supplier_raw_edges.append(
                SupplierRawEdge(
                    supplier_id=edge.supplier_id,
                    supplier_name=edge.supplier_name,
                    raw_product_id=edge.product_id,
                    raw_sku=edge.product_sku,
                    canonical_key=edge.canonical_key,
                    ingredient_family=edge.ingredient_family,
                    functional_role=edge.functional_role,
                )
            )

        # Aggregates
        all_fam_counter: Counter[str] = Counter()
        all_role_counter: Counter[str] = Counter()
        for m in canonical_by_raw_id.values():
            all_fam_counter[m.ingredient_family] += 1
            all_role_counter[m.functional_role] += 1

        aggregates = SupplyNetworkAggregates(
            n_companies=len(companies),
            n_suppliers=len(suppliers),
            n_finished_goods=len(finished_product_ids),
            n_raw_materials=len(raw_product_ids),
            n_supplier_products=len(supplier_product_edges),
            n_bom_edges=len(product_raw_edges),
            top_families=[(fam, cnt) for fam, cnt in all_fam_counter.most_common(10)],
            top_roles=[(role, cnt) for role, cnt in all_role_counter.most_common(10)],
            sole_source_raw_ids=sole_source_raw_ids,
        )

        return SupplyNetworkBundle(
            generated_at=datetime.now(UTC),
            aggregates=aggregates,
            companies=companies,
            suppliers=suppliers,
            products=products,
            supplier_product_edges=supplier_product_edges,
            company_supplier_edges=company_supplier_edges,
            product_raw_edges=product_raw_edges,
            supplier_raw_edges=supplier_raw_edges,
        )


__all__ = ["SupplyNetworkService"]
