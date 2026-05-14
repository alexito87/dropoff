from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel

from app.modules.payments.schemas.payment import (
    CheckoutSessionRead,
    PaymentRead,
    PaymentTransactionRead,
    StripeCheckoutSessionRead,
    StripePaymentConfirm,
    StripePaymentIntentRead,
)


class OrderCreate(BaseModel):
    delivery_method: str
    payment_method: str = "stripe_checkout"


class OrderItemRead(BaseModel):
    id: UUID
    item_id: UUID
    item_title: str
    owner_id: UUID
    owner_name: str | None = None
    rent_start: date
    rent_end: date
    days_count: int
    quantity: int
    daily_price_cents: int
    deposit_cents: int
    rent_total_cents: int
    total_deposit_cents: int
    line_total_cents: int
    status: str


class OrderRead(BaseModel):
    id: UUID
    status: str
    delivery_method: str
    payment_method: str
    items_total_cents: int
    deposit_total_cents: int
    delivery_fee_cents: int
    total_amount_cents: int
    stripe_checkout_session_id: str | None = None
    stripe_payment_intent_id: str | None = None
    payment: PaymentRead | None = None
    items: list[OrderItemRead]
    created_at: datetime
    updated_at: datetime
    paid_at: datetime | None = None


__all__ = [
    "OrderCreate",
    "OrderItemRead",
    "OrderRead",
    "PaymentRead",
    "PaymentTransactionRead",
    "StripeCheckoutSessionRead",
    "StripePaymentIntentRead",
    "CheckoutSessionRead",
    "StripePaymentConfirm",
]