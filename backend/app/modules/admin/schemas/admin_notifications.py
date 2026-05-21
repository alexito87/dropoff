from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AdminNotificationUserRead(BaseModel):
    id: UUID
    email: str
    full_name: str | None = None
    is_active: bool
    email_verified: bool


class AdminNotificationRead(BaseModel):
    id: UUID
    user_id: UUID
    user: AdminNotificationUserRead | None = None
    type: str
    payload: dict
    is_read: bool
    created_at: datetime


class AdminNotificationsResponse(BaseModel):
    notifications: list[AdminNotificationRead]
    page: int
    page_size: int
    total: int
    pages: int


class AdminServiceNotificationCreate(BaseModel):
    user_id: UUID
    type: str = Field(default="service_notification", min_length=1, max_length=100)
    payload: dict = Field(default_factory=dict)
    reason: str | None = Field(default=None, max_length=500)


class AdminNotificationActionPayload(BaseModel):
    reason: str | None = Field(default=None, max_length=500)