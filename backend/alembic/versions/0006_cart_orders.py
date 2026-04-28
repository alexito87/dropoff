"""add cart and order tables"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0006_cart_orders"
down_revision = "20260415_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "carts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_carts_user_id", "carts", ["user_id"])
    op.create_index("ix_carts_status", "carts", ["status"])
    op.create_index("ix_carts_user_status", "carts", ["user_id", "status"])

    op.create_table(
        "cart_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cart_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rent_start", sa.Date(), nullable=False),
        sa.Column("rent_end", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("daily_price_cents", sa.Integer(), nullable=False),
        sa.Column("deposit_cents", sa.Integer(), nullable=False),
        sa.Column("rent_total_cents", sa.Integer(), nullable=False),
        sa.Column("total_deposit_cents", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["cart_id"], ["carts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cart_items_cart_id", "cart_items", ["cart_id"])
    op.create_index("ix_cart_items_item_id", "cart_items", ["item_id"])
    op.create_index("ix_cart_items_cart_item_dates", "cart_items", ["cart_id", "item_id", "rent_start", "rent_end"])

    op.create_table(
        "orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cart_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("delivery_method", sa.String(length=50), nullable=False),
        sa.Column("payment_method", sa.String(length=50), nullable=False),
        sa.Column("items_total_cents", sa.Integer(), nullable=False),
        sa.Column("deposit_total_cents", sa.Integer(), nullable=False),
        sa.Column("delivery_fee_cents", sa.Integer(), nullable=False),
        sa.Column("total_amount_cents", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["cart_id"], ["carts.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_orders_user_id", "orders", ["user_id"])
    op.create_index("ix_orders_cart_id", "orders", ["cart_id"])
    op.create_index("ix_orders_status", "orders", ["status"])
    op.create_index("ix_orders_user_status", "orders", ["user_id", "status"])

    op.create_table(
        "order_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rent_start", sa.Date(), nullable=False),
        sa.Column("rent_end", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("daily_price_cents", sa.Integer(), nullable=False),
        sa.Column("deposit_cents", sa.Integer(), nullable=False),
        sa.Column("rent_total_cents", sa.Integer(), nullable=False),
        sa.Column("total_deposit_cents", sa.Integer(), nullable=False),
        sa.Column("line_total_cents", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"])
    op.create_index("ix_order_items_item_id", "order_items", ["item_id"])
    op.create_index("ix_order_items_owner_id", "order_items", ["owner_id"])
    op.create_index("ix_order_items_status", "order_items", ["status"])
    op.create_index("ix_order_items_order", "order_items", ["order_id"])
    op.create_index("ix_order_items_item_dates", "order_items", ["item_id", "rent_start", "rent_end"])


def downgrade() -> None:
    op.drop_index("ix_order_items_item_dates", table_name="order_items")
    op.drop_index("ix_order_items_order", table_name="order_items")
    op.drop_index("ix_order_items_status", table_name="order_items")
    op.drop_index("ix_order_items_owner_id", table_name="order_items")
    op.drop_index("ix_order_items_item_id", table_name="order_items")
    op.drop_index("ix_order_items_order_id", table_name="order_items")
    op.drop_table("order_items")

    op.drop_index("ix_orders_user_status", table_name="orders")
    op.drop_index("ix_orders_status", table_name="orders")
    op.drop_index("ix_orders_cart_id", table_name="orders")
    op.drop_index("ix_orders_user_id", table_name="orders")
    op.drop_table("orders")

    op.drop_index("ix_cart_items_cart_item_dates", table_name="cart_items")
    op.drop_index("ix_cart_items_item_id", table_name="cart_items")
    op.drop_index("ix_cart_items_cart_id", table_name="cart_items")
    op.drop_table("cart_items")

    op.drop_index("ix_carts_user_status", table_name="carts")
    op.drop_index("ix_carts_status", table_name="carts")
    op.drop_index("ix_carts_user_id", table_name="carts")
    op.drop_table("carts")
