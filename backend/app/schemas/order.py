from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


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


class PaymentRead(BaseModel):
    id: UUID
    status: str
    provider: str
    payment_method: str
    amount_total_cents: int
    currency: str
    stripe_checkout_session_id: str | None = None
    stripe_payment_intent_id: str | None = None
    created_at: datetime
    updated_at: datetime
    paid_at: datetime | None = None
    failed_at: datetime | None = None
    cancelled_at: datetime | None = None


class PaymentTransactionRead(BaseModel):
    id: UUID
    type: str
    status: str
    provider: str
    provider_tx_id: str | None = None
    amount_cents: int
    currency: str
    error_message: str | None = None
    created_at: datetime


class StripeCheckoutSessionRead(BaseModel):
    id: UUID
    provider_session_id: str | None = None
    status: str
    payment_status: str | None = None
    checkout_url: str | None = None
    amount_total_cents: int
    currency: str
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    expired_at: datetime | None = None


class StripePaymentIntentRead(BaseModel):
    id: UUID
    provider_payment_intent_id: str
    status: str
    amount_cents: int
    currency: str
    latest_charge_id: str | None = None
    created_at: datetime
    updated_at: datetime
    succeeded_at: datetime | None = None
    canceled_at: datetime | None = None


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


class CheckoutSessionRead(BaseModel):
    order_id: UUID
    payment_id: UUID
    checkout_url: str
    stripe_checkout_session_id: str | None = None
    local_checkout_session_id: UUID | None = None


class StripePaymentConfirm(BaseModel):
    stripe_checkout_session_id: str
