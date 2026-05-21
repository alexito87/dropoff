from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AdminUserRead(BaseModel):
    id: UUID
    email: str
    full_name: str | None = None
    phone: str | None = None
    city: str | None = None
    is_active: bool
    is_superuser: bool
    email_verified: bool
    created_at: datetime
    updated_at: datetime


class AdminUsersResponse(BaseModel):
    users: list[AdminUserRead]
    page: int
    page_size: int
    total: int
    pages: int


class AdminUserProfileResetPayload(BaseModel):
    reset_full_name: bool = True
    reset_phone: bool = True
    reset_city: bool = True
    reason: str | None = Field(default=None, max_length=500)


class AdminUserSuperuserPayload(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class AdminUserStatusPayload(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class AdminUserRelatedSummary(BaseModel):
    user_id: UUID
    email: str

    items_total: int
    items_by_status: dict[str, int]

    rentals_as_renter_total: int
    rentals_as_renter_by_status: dict[str, int]

    rentals_as_owner_total: int
    rentals_as_owner_by_status: dict[str, int]

    carts_total: int
    carts_by_status: dict[str, int]
    cart_items_total: int

    orders_total: int
    orders_by_status: dict[str, int]
    order_items_as_owner_total: int
    order_items_as_owner_by_status: dict[str, int]

    payments_total: int
    payments_by_status: dict[str, int]

    deliveries_as_renter_total: int
    deliveries_as_renter_by_status: dict[str, int]

    deliveries_as_owner_total: int
    deliveries_as_owner_by_status: dict[str, int]

    notifications_total: int
    unread_notifications_total: int
    notifications_by_type: dict[str, int]