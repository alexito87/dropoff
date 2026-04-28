from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CartItemCreate(BaseModel):
    item_id: UUID
    rent_start: date
    rent_end: date
    quantity: int = Field(default=1, ge=1, le=1)


class CartItemRead(BaseModel):
    id: UUID
    item_id: UUID
    item_title: str
    owner_id: UUID
    owner_name: str | None = None
    image_url: str | None = None
    rent_start: date
    rent_end: date
    days_count: int
    quantity: int
    daily_price_cents: int
    deposit_cents: int
    rent_total_cents: int
    total_deposit_cents: int
    line_total_cents: int
    created_at: datetime


class CartRead(BaseModel):
    id: UUID | None = None
    status: str = "active"
    items: list[CartItemRead] = []
    items_total_cents: int = 0
    deposit_total_cents: int = 0
    payable_total_cents: int = 0
    items_count: int = 0
