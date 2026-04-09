from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class RentalCreate(BaseModel):
    item_id: UUID
    start_date: date
    end_date: date


class RentalDecisionPayload(BaseModel):
    owner_comment: str | None = Field(default=None, max_length=2000)


class RentalRead(BaseModel):
    id: UUID
    item_id: UUID
    item_title: str
    renter_id: UUID
    renter_name: str | None = None
    owner_id: UUID
    owner_name: str | None = None
    status: str
    start_date: date
    end_date: date
    days_count: int
    daily_price_cents: int
    deposit_cents: int
    total_estimate_cents: int
    owner_comment: str | None = None
    created_at: datetime
    updated_at: datetime