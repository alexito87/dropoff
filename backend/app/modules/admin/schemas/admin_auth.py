from pydantic import BaseModel, Field


class AdminAuthActionPayload(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class AdminResendVerificationPayload(BaseModel):
    reason: str | None = Field(default=None, max_length=500)
    expire_previous_tokens: bool = True