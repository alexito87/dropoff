"""add stripe checkout fields to orders"""

from alembic import op
import sqlalchemy as sa


revision = "0008_stripe_checkout_fields"
down_revision = "0006_cart_orders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("stripe_checkout_session_id", sa.String(length=255), nullable=True))
    op.add_column("orders", sa.Column("stripe_payment_intent_id", sa.String(length=255), nullable=True))
    op.create_index("ix_orders_stripe_checkout_session_id", "orders", ["stripe_checkout_session_id"])
    op.create_index("ix_orders_stripe_payment_intent_id", "orders", ["stripe_payment_intent_id"])

    op.execute("UPDATE orders SET payment_method = 'stripe_checkout' WHERE payment_method = 'stripe_sandbox'")


def downgrade() -> None:
    op.drop_index("ix_orders_stripe_payment_intent_id", table_name="orders")
    op.drop_index("ix_orders_stripe_checkout_session_id", table_name="orders")
    op.drop_column("orders", "stripe_payment_intent_id")
    op.drop_column("orders", "stripe_checkout_session_id")
