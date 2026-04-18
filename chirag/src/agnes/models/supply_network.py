"""Pydantic contracts for the supply-network dashboard bundle."""

from __future__ import annotations

from datetime import datetime
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

SUPPLY_NETWORK_SCHEMA_VERSION: Final[str] = "1.0.0"

ProductType = Literal["finished-good", "raw-material"]


class CompanyNode(BaseModel):
    """One procurer/company row with basic fan-out counts."""

    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    finished_good_count: int = Field(ge=0)
    raw_material_count: int = Field(ge=0)
    supplier_count: int = Field(ge=0)


class SupplierNode(BaseModel):
    """One supplier row with popularity / reach counts."""

    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    product_count: int = Field(ge=0)
    canonical_key_count: int = Field(ge=0)
    company_count: int = Field(ge=0)
    sole_source_count: int = Field(ge=0)
    top_families: list[str] = Field(default_factory=list)


class ProductNode(BaseModel):
    """One product row (finished or raw) with optional registry enrichment."""

    model_config = ConfigDict(extra="forbid")

    id: int
    sku: str
    company_id: int
    company_name: str
    type: ProductType
    normalized_name: str | None = None
    canonical_key: str | None = None
    ingredient_family: str | None = None
    functional_role: str | None = None
    confidence: float | None = None
    supplier_count: int | None = None
    bom_count: int | None = None


class SupplierProductEdge(BaseModel):
    """Edge in the Supplier_Product join (raw-material by convention)."""

    model_config = ConfigDict(extra="forbid")

    supplier_id: int
    supplier_name: str
    product_id: int
    product_sku: str
    company_id: int
    company_name: str
    canonical_key: str | None = None
    ingredient_family: str | None = None
    functional_role: str | None = None


class CompanySupplierEdge(BaseModel):
    """Derived procurer-supplier edge with shared raw-product count."""

    model_config = ConfigDict(extra="forbid")

    company_id: int
    company_name: str
    supplier_id: int
    supplier_name: str
    shared_raw_count: int = Field(ge=0)
    canonical_keys: list[str] = Field(default_factory=list)


class ProductRawEdge(BaseModel):
    """BOM line: finished product -> raw material it consumes."""

    model_config = ConfigDict(extra="forbid")

    finished_product_id: int
    finished_sku: str
    company_id: int
    company_name: str
    raw_product_id: int
    raw_sku: str
    canonical_key: str | None = None
    ingredient_family: str | None = None


class SupplierRawEdge(BaseModel):
    """Supplier_Product edge filtered to canonicalized raw materials."""

    model_config = ConfigDict(extra="forbid")

    supplier_id: int
    supplier_name: str
    raw_product_id: int
    raw_sku: str
    canonical_key: str
    ingredient_family: str | None = None
    functional_role: str | None = None


class SupplyNetworkAggregates(BaseModel):
    """Top-level counts + distribution summaries for the section header."""

    model_config = ConfigDict(extra="forbid")

    n_companies: int = Field(ge=0)
    n_suppliers: int = Field(ge=0)
    n_finished_goods: int = Field(ge=0)
    n_raw_materials: int = Field(ge=0)
    n_supplier_products: int = Field(ge=0)
    n_bom_edges: int = Field(ge=0)
    top_families: list[tuple[str, int]] = Field(default_factory=list)
    top_roles: list[tuple[str, int]] = Field(default_factory=list)
    sole_source_raw_ids: list[int] = Field(default_factory=list)


class SupplyNetworkBundle(BaseModel):
    """One-shot supply-network payload consumed by the dashboard."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = SUPPLY_NETWORK_SCHEMA_VERSION
    generated_at: datetime
    aggregates: SupplyNetworkAggregates
    companies: list[CompanyNode] = Field(default_factory=list)
    suppliers: list[SupplierNode] = Field(default_factory=list)
    products: list[ProductNode] = Field(default_factory=list)
    supplier_product_edges: list[SupplierProductEdge] = Field(default_factory=list)
    company_supplier_edges: list[CompanySupplierEdge] = Field(default_factory=list)
    product_raw_edges: list[ProductRawEdge] = Field(default_factory=list)
    supplier_raw_edges: list[SupplierRawEdge] = Field(default_factory=list)
