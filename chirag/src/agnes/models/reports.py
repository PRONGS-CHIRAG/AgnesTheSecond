"""Structured outputs for Phase 1 reports."""

from typing import Literal

from pydantic import BaseModel, Field


class ColumnInfo(BaseModel):
    name: str
    type: str | None = None
    nullable: bool = True


class ForeignKeyInfo(BaseModel):
    constrained_columns: list[str]
    referred_table: str
    referred_columns: list[str]


class TableSummary(BaseModel):
    name: str
    row_count: int
    columns: list[ColumnInfo]
    primary_key: list[str] = Field(default_factory=list)
    foreign_keys: list[ForeignKeyInfo] = Field(default_factory=list)


class SchemaSummary(BaseModel):
    tables: list[TableSummary]


class EntityCounts(BaseModel):
    Company: int
    Product: int
    FinishedGood: int
    RawMaterial: int
    BOM: int
    BOM_Component: int
    Supplier: int
    Supplier_Product: int


class RepeatedMaterial(BaseModel):
    raw_product_id: int
    sku: str
    n_boms: int
    n_finished_goods: int
    n_companies: int
    supplier_count: int
    supplier_ids: list[int]


ConcentrationNote = Literal["single-sourced", "fragmented", "well-distributed"]


class SupplierFragmentation(BaseModel):
    raw_product_id: int
    sku: str
    supplier_count: int
    supplier_names: list[str]
    n_finished_goods_using: int
    concentration_note: ConcentrationNote


class Phase1Report(BaseModel):
    entity_counts: EntityCounts
    repeated_materials: list[RepeatedMaterial]
    supplier_fragmentation: list[SupplierFragmentation]
    top_repeated_materials_preview: list[RepeatedMaterial] = Field(default_factory=list)
    top_supplier_fragmentation_preview: list[SupplierFragmentation] = Field(default_factory=list)
