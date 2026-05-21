from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CatalogAdminOwner(BaseModel):
    id: UUID | None = None
    email: str | None = None
    full_name: str | None = None
    city: str | None = None
    is_active: bool | None = None
    email_verified: bool | None = None


class CatalogAdminCategory(BaseModel):
    id: UUID | None = None
    name: str | None = None


class CatalogAdminItemImage(BaseModel):
    id: UUID
    url: str
    versioned_url: str
    storage_path: str | None = None
    mime_type: str | None = None
    file_size_bytes: int | None = None
    sort_order: int
    version: int
    created_at: datetime


class CatalogAdminItemCard(BaseModel):
    id: UUID
    owner_id: UUID
    owner_email: str | None = None
    owner_name: str | None = None
    category_id: UUID
    category_name: str | None = None

    title: str
    description: str | None = None
    city: str
    pickup_address: str | None = None

    status: str
    daily_price_cents: int
    deposit_cents: int

    images_count: int
    preview_image_url: str | None = None

    moderated_by: UUID | None = None
    moderated_at: datetime | None = None
    moderation_comment: str | None = None

    created_at: datetime
    updated_at: datetime


class CatalogAdminItemsResponse(BaseModel):
    items: list[CatalogAdminItemCard]
    page: int
    page_size: int
    total: int
    pages: int


class CatalogAdminItemDetails(BaseModel):
    id: UUID
    owner_id: UUID
    category_id: UUID

    title: str
    description: str | None = None
    city: str
    pickup_address: str | None = None

    status: str
    daily_price_cents: int
    deposit_cents: int

    moderated_by: UUID | None = None
    moderated_at: datetime | None = None
    moderation_comment: str | None = None

    created_at: datetime
    updated_at: datetime

    owner: CatalogAdminOwner | None = None
    category: CatalogAdminCategory | None = None
    images: list[CatalogAdminItemImage]