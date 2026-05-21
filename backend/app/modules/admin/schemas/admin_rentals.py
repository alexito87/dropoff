from pydantic import BaseModel, Field


class AdminRentalActionPayload(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class AdminRentalForceStatusPayload(BaseModel):
    status: str = Field(min_length=1, max_length=100)
    reason: str | None = Field(default=None, max_length=1000)