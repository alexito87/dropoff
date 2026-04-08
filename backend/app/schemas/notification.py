
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class NotificationRead(BaseModel):
    id: UUID
    user_id: UUID
    type: str
    payload: dict = Field(default_factory=dict)
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}