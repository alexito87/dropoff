from pydantic import BaseModel, Field


class AdminPaymentActionPayload(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class AdminPaymentRetryCheckoutPayload(BaseModel):
    reason: str | None = Field(default=None, max_length=500)
    clear_stripe_references: bool = True