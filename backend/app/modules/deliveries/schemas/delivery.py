from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DeliveryCreate(BaseModel):
    order_item_id: UUID
    courier_name: str | None = Field(default=None, max_length=255)
    current_location: str | None = Field(default=None, max_length=500)
    started_at: datetime | None = None


class DeliveryComplete(BaseModel):
    final_location: str | None = Field(default=None, max_length=500)
    finished_at: datetime | None = None


class DeliveryReturnRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)


class DeliveryRead(BaseModel):
    id: UUID
    order_id: UUID
    order_item_id: UUID
    item_id: UUID
    renter_id: UUID
    owner_id: UUID

    status: str
    courier_name: str | None = None
    current_location: str | None = None
    final_location: str | None = None
    return_reason: str | None = None

    started_at: datetime
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}