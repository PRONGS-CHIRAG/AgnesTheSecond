"""Row shapes aligned with SQLite tables."""

from pydantic import BaseModel


class CompanyRow(BaseModel):
    Id: int
    Name: str


class ProductRow(BaseModel):
    Id: int
    SKU: str
    CompanyId: int
    Type: str  # 'finished-good' | 'raw-material'


class BOMRow(BaseModel):
    Id: int
    ProducedProductId: int


class BOMComponentRow(BaseModel):
    BOMId: int
    ConsumedProductId: int


class SupplierRow(BaseModel):
    Id: int
    Name: str


class SupplierProductRow(BaseModel):
    SupplierId: int
    ProductId: int
