from pydantic import BaseModel, Field


class AdminModerationDecisionPayload(BaseModel):
    comment: str | None = Field(default=None, max_length=1000)


class AdminEmailVerificationPayload(BaseModel):
    reason: str | None = Field(default=None, max_length=500)