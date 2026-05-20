"""create event projection tables

Revision ID: 20260520_0002
Revises: 20260520_0001
Create Date: 2026-05-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260520_0002"
down_revision: Union[str, None] = "20260520_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _projection_common_columns() -> list[sa.Column]:
    return [
        sa.Column("source_event_id", sa.String(length=100), nullable=False),
        sa.Column("source_event_type", sa.String(length=150), nullable=False),
        sa.Column("source_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "projected_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    ]


def _create_common_indexes(table_name: str) -> None:
    op.create_index(f"ix_{table_name}_source_event_id", table_name, ["source_event_id"])
    op.create_index(f"ix_{table_name}_source_event_type", table_name, ["source_event_type"])


def upgrade() -> None:
    op.create_table(
        "catalog_item_projections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_id", sa.String(length=100), nullable=False),
        sa.Column("owner_id", sa.String(length=100), nullable=True),
        sa.Column("category_id", sa.String(length=100), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("daily_price_cents", sa.Integer(), nullable=True),
        sa.Column("deposit_cents", sa.Integer(), nullable=True),
        *_projection_common_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("item_id", name="uq_catalog_item_projections_item_id"),
    )
    op.create_index("ix_catalog_item_projections_item_id", "catalog_item_projections", ["item_id"])
    op.create_index("ix_catalog_item_projections_owner_id", "catalog_item_projections", ["owner_id"])
    op.create_index("ix_catalog_item_projections_category_id", "catalog_item_projections", ["category_id"])
    op.create_index("ix_catalog_item_projections_status", "catalog_item_projections", ["status"])
    _create_common_indexes("catalog_item_projections")

    op.create_table(
        "moderation_item_projections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_id", sa.String(length=100), nullable=False),
        sa.Column("owner_id", sa.String(length=100), nullable=True),
        sa.Column("category_id", sa.String(length=100), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("item_status", sa.String(length=50), nullable=True),
        sa.Column("moderation_status", sa.String(length=50), nullable=True),
        sa.Column("moderation_comment", sa.Text(), nullable=True),
        *_projection_common_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("item_id", name="uq_moderation_item_projections_item_id"),
    )
    op.create_index("ix_moderation_item_projections_item_id", "moderation_item_projections", ["item_id"])
    op.create_index("ix_moderation_item_projections_owner_id", "moderation_item_projections", ["owner_id"])
    op.create_index("ix_moderation_item_projections_category_id", "moderation_item_projections", ["category_id"])
    op.create_index("ix_moderation_item_projections_item_status", "moderation_item_projections", ["item_status"])
    op.create_index("ix_moderation_item_projections_moderation_status", "moderation_item_projections", ["moderation_status"])
    _create_common_indexes("moderation_item_projections")

    op.create_table(
        "orders_item_projections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_id", sa.String(length=100), nullable=False),
        sa.Column("owner_id", sa.String(length=100), nullable=True),
        sa.Column("category_id", sa.String(length=100), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("daily_price_cents", sa.Integer(), nullable=True),
        sa.Column("deposit_cents", sa.Integer(), nullable=True),
        *_projection_common_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("item_id", name="uq_orders_item_projections_item_id"),
    )
    op.create_index("ix_orders_item_projections_item_id", "orders_item_projections", ["item_id"])
    op.create_index("ix_orders_item_projections_owner_id", "orders_item_projections", ["owner_id"])
    op.create_index("ix_orders_item_projections_category_id", "orders_item_projections", ["category_id"])
    op.create_index("ix_orders_item_projections_status", "orders_item_projections", ["status"])
    _create_common_indexes("orders_item_projections")

    op.create_table(
        "orders_cart_projections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cart_id", sa.String(length=100), nullable=False),
        sa.Column("user_id", sa.String(length=100), nullable=True),
        sa.Column("cart_status", sa.String(length=50), nullable=True),
        sa.Column("last_order_id", sa.String(length=100), nullable=True),
        sa.Column("last_order_status", sa.String(length=50), nullable=True),
        sa.Column("items_count", sa.Integer(), nullable=True),
        sa.Column("total_amount_cents", sa.Integer(), nullable=True),
        *_projection_common_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cart_id", name="uq_orders_cart_projections_cart_id"),
    )
    op.create_index("ix_orders_cart_projections_cart_id", "orders_cart_projections", ["cart_id"])
    op.create_index("ix_orders_cart_projections_user_id", "orders_cart_projections", ["user_id"])
    op.create_index("ix_orders_cart_projections_cart_status", "orders_cart_projections", ["cart_status"])
    op.create_index("ix_orders_cart_projections_last_order_id", "orders_cart_projections", ["last_order_id"])
    _create_common_indexes("orders_cart_projections")

    op.create_table(
        "payments_order_projections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", sa.String(length=100), nullable=False),
        sa.Column("user_id", sa.String(length=100), nullable=True),
        sa.Column("order_status", sa.String(length=50), nullable=True),
        sa.Column("payment_method", sa.String(length=50), nullable=True),
        sa.Column("total_amount_cents", sa.Integer(), nullable=True),
        *_projection_common_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id", name="uq_payments_order_projections_order_id"),
    )
    op.create_index("ix_payments_order_projections_order_id", "payments_order_projections", ["order_id"])
    op.create_index("ix_payments_order_projections_user_id", "payments_order_projections", ["user_id"])
    op.create_index("ix_payments_order_projections_order_status", "payments_order_projections", ["order_status"])
    _create_common_indexes("payments_order_projections")

    op.create_table(
        "deliveries_order_projections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", sa.String(length=100), nullable=False),
        sa.Column("user_id", sa.String(length=100), nullable=True),
        sa.Column("order_status", sa.String(length=50), nullable=True),
        sa.Column("delivery_method", sa.String(length=50), nullable=True),
        sa.Column("total_amount_cents", sa.Integer(), nullable=True),
        *_projection_common_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id", name="uq_deliveries_order_projections_order_id"),
    )
    op.create_index("ix_deliveries_order_projections_order_id", "deliveries_order_projections", ["order_id"])
    op.create_index("ix_deliveries_order_projections_user_id", "deliveries_order_projections", ["user_id"])
    op.create_index("ix_deliveries_order_projections_order_status", "deliveries_order_projections", ["order_status"])
    _create_common_indexes("deliveries_order_projections")

    op.create_table(
        "orders_payment_projections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_id", sa.String(length=100), nullable=False),
        sa.Column("order_id", sa.String(length=100), nullable=True),
        sa.Column("payer_user_id", sa.String(length=100), nullable=True),
        sa.Column("payment_status", sa.String(length=50), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=True),
        sa.Column("payment_method", sa.String(length=50), nullable=True),
        sa.Column("amount_total_cents", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=True),
        sa.Column("stripe_checkout_session_id", sa.String(length=255), nullable=True),
        sa.Column("stripe_payment_intent_id", sa.String(length=255), nullable=True),
        *_projection_common_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payment_id", name="uq_orders_payment_projections_payment_id"),
    )
    op.create_index("ix_orders_payment_projections_payment_id", "orders_payment_projections", ["payment_id"])
    op.create_index("ix_orders_payment_projections_order_id", "orders_payment_projections", ["order_id"])
    op.create_index("ix_orders_payment_projections_payer_user_id", "orders_payment_projections", ["payer_user_id"])
    op.create_index("ix_orders_payment_projections_payment_status", "orders_payment_projections", ["payment_status"])
    _create_common_indexes("orders_payment_projections")

    op.create_table(
        "orders_delivery_projections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("delivery_id", sa.String(length=100), nullable=False),
        sa.Column("order_id", sa.String(length=100), nullable=True),
        sa.Column("order_item_id", sa.String(length=100), nullable=True),
        sa.Column("item_id", sa.String(length=100), nullable=True),
        sa.Column("renter_id", sa.String(length=100), nullable=True),
        sa.Column("owner_id", sa.String(length=100), nullable=True),
        sa.Column("delivery_status", sa.String(length=50), nullable=True),
        sa.Column("current_location", sa.String(length=500), nullable=True),
        sa.Column("final_location", sa.String(length=500), nullable=True),
        sa.Column("return_reason", sa.Text(), nullable=True),
        *_projection_common_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("delivery_id", name="uq_orders_delivery_projections_delivery_id"),
    )
    op.create_index("ix_orders_delivery_projections_delivery_id", "orders_delivery_projections", ["delivery_id"])
    op.create_index("ix_orders_delivery_projections_order_id", "orders_delivery_projections", ["order_id"])
    op.create_index("ix_orders_delivery_projections_order_item_id", "orders_delivery_projections", ["order_item_id"])
    op.create_index("ix_orders_delivery_projections_item_id", "orders_delivery_projections", ["item_id"])
    op.create_index("ix_orders_delivery_projections_renter_id", "orders_delivery_projections", ["renter_id"])
    op.create_index("ix_orders_delivery_projections_owner_id", "orders_delivery_projections", ["owner_id"])
    op.create_index("ix_orders_delivery_projections_delivery_status", "orders_delivery_projections", ["delivery_status"])
    _create_common_indexes("orders_delivery_projections")

    op.create_table(
        "notifications_user_projections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("email_verified", sa.Boolean(), nullable=True),
        sa.Column("is_superuser", sa.Boolean(), nullable=True),
        *_projection_common_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_notifications_user_projections_user_id"),
    )
    op.create_index("ix_notifications_user_projections_user_id", "notifications_user_projections", ["user_id"])
    op.create_index("ix_notifications_user_projections_email", "notifications_user_projections", ["email"])
    _create_common_indexes("notifications_user_projections")

    op.create_table(
        "audit_domain_event_projections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_event_id", sa.String(length=100), nullable=False),
        sa.Column("source_event_type", sa.String(length=150), nullable=False),
        sa.Column("topic", sa.String(length=200), nullable=True),
        sa.Column("producer", sa.String(length=150), nullable=True),
        sa.Column("aggregate_type", sa.String(length=100), nullable=True),
        sa.Column("aggregate_id", sa.String(length=100), nullable=True),
        sa.Column("source_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "projected_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_event_id", name="uq_audit_domain_event_projections_source_event_id"),
    )
    op.create_index("ix_audit_domain_event_projections_source_event_id", "audit_domain_event_projections", ["source_event_id"])
    op.create_index("ix_audit_domain_event_projections_source_event_type", "audit_domain_event_projections", ["source_event_type"])
    op.create_index("ix_audit_domain_event_projections_topic", "audit_domain_event_projections", ["topic"])
    op.create_index("ix_audit_domain_event_projections_producer", "audit_domain_event_projections", ["producer"])
    op.create_index("ix_audit_domain_event_projections_aggregate_type", "audit_domain_event_projections", ["aggregate_type"])
    op.create_index("ix_audit_domain_event_projections_aggregate_id", "audit_domain_event_projections", ["aggregate_id"])


def downgrade() -> None:
    op.drop_table("audit_domain_event_projections")
    op.drop_table("notifications_user_projections")
    op.drop_table("orders_delivery_projections")
    op.drop_table("orders_payment_projections")
    op.drop_table("deliveries_order_projections")
    op.drop_table("payments_order_projections")
    op.drop_table("orders_cart_projections")
    op.drop_table("orders_item_projections")
    op.drop_table("moderation_item_projections")
    op.drop_table("catalog_item_projections")