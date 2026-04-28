import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_user_status", "user_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    cart_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("carts.id"), nullable=True, index=True)

    status: Mapped[str] = mapped_column(String(50), nullable=False, default="awaiting_payment", index=True)
    delivery_method: Mapped[str] = mapped_column(String(50), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(50), nullable=False, default="stripe_checkout")

    stripe_checkout_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    items_total_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    deposit_total_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    delivery_fee_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    total_amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User")
    cart = relationship("Cart")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan", order_by="OrderItem.created_at")


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        Index("ix_order_items_order", "order_id"),
        Index("ix_order_items_item_dates", "item_id", "rent_start", "rent_end"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("items.id"), nullable=False, index=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    rent_start: Mapped[date] = mapped_column(Date, nullable=False)
    rent_end: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="awaiting_payment", index=True)

    daily_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    deposit_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    rent_total_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    total_deposit_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    line_total_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    order = relationship("Order", back_populates="items")
    item = relationship("Item")
    owner = relationship("User")
