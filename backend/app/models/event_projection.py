import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class CatalogItemProjection(Base):
    __tablename__ = "catalog_item_projections"
    __table_args__ = (
        UniqueConstraint("item_id", name="uq_catalog_item_projections_item_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    item_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    owner_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    category_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)

    daily_price_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deposit_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)

    source_event_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_event_type: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    source_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    projected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ModerationItemProjection(Base):
    __tablename__ = "moderation_item_projections"
    __table_args__ = (
        UniqueConstraint("item_id", name="uq_moderation_item_projections_item_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    item_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    owner_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    category_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    item_status: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    moderation_status: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    moderation_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    source_event_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_event_type: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    source_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    projected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class OrdersItemProjection(Base):
    __tablename__ = "orders_item_projections"
    __table_args__ = (
        UniqueConstraint("item_id", name="uq_orders_item_projections_item_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    item_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    owner_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    category_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)

    daily_price_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deposit_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)

    source_event_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_event_type: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    source_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    projected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class OrdersCartProjection(Base):
    __tablename__ = "orders_cart_projections"
    __table_args__ = (
        UniqueConstraint("cart_id", name="uq_orders_cart_projections_cart_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    cart_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    user_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    cart_status: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    last_order_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    last_order_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    items_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_amount_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)

    source_event_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_event_type: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    source_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    projected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class PaymentsOrderProjection(Base):
    __tablename__ = "payments_order_projections"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_payments_order_projections_order_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    order_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    user_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    order_status: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    total_amount_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)

    source_event_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_event_type: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    source_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    projected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class DeliveriesOrderProjection(Base):
    __tablename__ = "deliveries_order_projections"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_deliveries_order_projections_order_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    order_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    user_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    order_status: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    delivery_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    total_amount_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)

    source_event_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_event_type: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    source_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    projected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class OrdersPaymentProjection(Base):
    __tablename__ = "orders_payment_projections"
    __table_args__ = (
        UniqueConstraint("payment_id", name="uq_orders_payment_projections_payment_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    payment_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    order_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    payer_user_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    payment_status: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    amount_total_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)

    stripe_checkout_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    source_event_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_event_type: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    source_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    projected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class OrdersDeliveryProjection(Base):
    __tablename__ = "orders_delivery_projections"
    __table_args__ = (
        UniqueConstraint("delivery_id", name="uq_orders_delivery_projections_delivery_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    delivery_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    order_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    order_item_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    item_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    renter_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    owner_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    delivery_status: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    current_location: Mapped[str | None] = mapped_column(String(500), nullable=True)
    final_location: Mapped[str | None] = mapped_column(String(500), nullable=True)
    return_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    source_event_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_event_type: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    source_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    projected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class NotificationsUserProjection(Base):
    __tablename__ = "notifications_user_projections"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_notifications_user_projections_user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_verified: Mapped[bool | None] = mapped_column(nullable=True)
    is_superuser: Mapped[bool | None] = mapped_column(nullable=True)

    source_event_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_event_type: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    source_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    projected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class AuditDomainEventProjection(Base):
    __tablename__ = "audit_domain_event_projections"
    __table_args__ = (
        UniqueConstraint("source_event_id", name="uq_audit_domain_event_projections_source_event_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    source_event_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_event_type: Mapped[str] = mapped_column(String(150), nullable=False, index=True)

    topic: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    producer: Mapped[str | None] = mapped_column(String(150), nullable=True, index=True)
    aggregate_type: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    aggregate_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    source_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    projected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )