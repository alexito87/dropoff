from pydantic import BaseModel, Field


class AdminStatusChangePayload(BaseModel):
    status: str = Field(min_length=1, max_length=100)
    reason: str | None = Field(default=None, max_length=500)


class AdminDlqActionPayload(BaseModel):
    reason: str | None = Field(default=None, max_length=500)