from datetime import datetime

from pydantic import BaseModel, Field


class AdminDeliveryActionPayload(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class AdminDeliveryCompletePayload(BaseModel):
    final_location: str | None = Field(default=None, max_length=500)
    finished_at: datetime | None = None
    reason: str | None = Field(default=None, max_length=1000)


class AdminDeliveryReturnRequestedPayload(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)