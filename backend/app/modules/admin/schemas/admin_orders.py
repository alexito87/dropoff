from pydantic import BaseModel, Field


class AdminOrderActionPayload(BaseModel):
    reason: str | None = Field(default=None, max_length=500)