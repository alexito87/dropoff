from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CatalogItemImagePublic(BaseModel):
    id: UUID
    url: str
    versioned_url: str
    sort_order: int
    version: int

    model_config = {"from_attributes": True}


class CatalogOwnerPublic(BaseModel):
    id: UUID | None = None
    full_name: str | None = None
    city: str | None = None


class CatalogItemCard(BaseModel):
    id: UUID
    title: str
    city: str
    daily_price_cents: int
    deposit_cents: int
    category_id: UUID
    category_name: str
    preview_image_url: str | None = None
    created_at: datetime


class CatalogItemDetails(BaseModel):
    id: UUID
    title: str
    description: str
    city: str
    daily_price_cents: int
    deposit_cents: int
    category_id: UUID
    category_name: str
    images: list[CatalogItemImagePublic]
    owner: CatalogOwnerPublic


class CatalogItemsResponse(BaseModel):
    items: list[CatalogItemCard]
    page: int
    page_size: int
    total: int
    pages: int