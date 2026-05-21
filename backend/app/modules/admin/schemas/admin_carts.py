from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class AdminCartUserRead(BaseModel):
    id: UUID
    email: str
    full_name: str | None = None
    is_active: bool
    email_verified: bool


class AdminCartItemRead(BaseModel):
    id: UUID
    cart_id: UUID
    item_id: UUID
    item_title: str | None = None
    item_status: str | None = None
    owner_id: UUID | None = None
    owner_email: str | None = None

    rent_start: date
    rent_end: date
    quantity: int

    daily_price_cents: int
    deposit_cents: int
    rent_total_cents: int
    total_deposit_cents: int
    line_total_cents: int

    created_at: datetime
    updated_at: datetime


class AdminCartRead(BaseModel):
    id: UUID
    user_id: UUID
    status: str

    user: AdminCartUserRead | None = None

    items_count: int
    items_total_cents: int
    deposit_total_cents: int
    payable_total_cents: int

    created_at: datetime
    updated_at: datetime


class AdminCartDetailsRead(AdminCartRead):
    items: list[AdminCartItemRead]


class AdminCartsResponse(BaseModel):
    carts: list[AdminCartRead]
    page: int
    page_size: int
    total: int
    pages: int