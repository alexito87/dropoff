import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        Index("ix_payments_order_status", "order_id", "status"),
        Index("ix_payments_user_status", "payer_user_id", "status"),
        Index("ix_payments_stripe_checkout_session_id", "stripe_checkout_session_id"),
        Index("ix_payments_stripe_payment_intent_id", "stripe_payment_intent_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    payer_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending", index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="stripe")
    payment_method: Mapped[str] = mapped_column(String(50), nullable=False, default="stripe_checkout")

    amount_total_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="usd")

    stripe_checkout_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    order = relationship("Order")
    payer = relationship("User")
    checkout_sessions = relationship("StripeCheckoutSession", back_populates="payment", cascade="all, delete-orphan", order_by="StripeCheckoutSession.created_at")
    payment_intents = relationship("StripePaymentIntent", back_populates="payment", cascade="all, delete-orphan", order_by="StripePaymentIntent.created_at")
    transactions = relationship("PaymentTransaction", back_populates="payment", cascade="all, delete-orphan", order_by="PaymentTransaction.created_at")


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"
    __table_args__ = (
        Index("ix_payment_transactions_payment", "payment_id"),
        Index("ix_payment_transactions_order", "order_id"),
        Index("ix_payment_transactions_provider_tx", "provider", "provider_tx_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("payments.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)

    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="stripe")
    type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending", index=True)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="usd")
    provider_tx_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)

    payment = relationship("Payment", back_populates="transactions")
    order = relationship("Order")


class StripeCheckoutSession(Base):
    __tablename__ = "stripe_checkout_sessions"
    __table_args__ = (
        Index("ix_stripe_checkout_sessions_payment", "payment_id"),
        Index("ix_stripe_checkout_sessions_order", "order_id"),
        Index("ix_stripe_checkout_sessions_provider_session_id", "provider_session_id", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("payments.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    provider_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="creating", index=True)
    payment_status: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    checkout_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount_total_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="usd")

    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    payment = relationship("Payment", back_populates="checkout_sessions")
    order = relationship("Order")
    user = relationship("User")


class StripePaymentIntent(Base):
    __tablename__ = "stripe_payment_intents"
    __table_args__ = (
        Index("ix_stripe_payment_intents_payment", "payment_id"),
        Index("ix_stripe_payment_intents_order", "order_id"),
        Index("ix_stripe_payment_intents_provider_payment_intent_id", "provider_payment_intent_id", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("payments.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)

    provider_payment_intent_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="usd")
    latest_charge_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    succeeded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    payment = relationship("Payment", back_populates="payment_intents")
    order = relationship("Order")
