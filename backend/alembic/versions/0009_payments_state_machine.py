"""add payments state machine tables"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0009_payments_state_machine"
down_revision = "0008_stripe_checkout_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payer_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("payment_method", sa.String(length=50), nullable=False),
        sa.Column("amount_total_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("stripe_checkout_session_id", sa.String(length=255), nullable=True),
        sa.Column("stripe_payment_intent_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["payer_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payments_order_id", "payments", ["order_id"])
    op.create_index("ix_payments_payer_user_id", "payments", ["payer_user_id"])
    op.create_index("ix_payments_status", "payments", ["status"])
    op.create_index("ix_payments_order_status", "payments", ["order_id", "status"])
    op.create_index("ix_payments_user_status", "payments", ["payer_user_id", "status"])
    op.create_index("ix_payments_stripe_checkout_session_id", "payments", ["stripe_checkout_session_id"])
    op.create_index("ix_payments_stripe_payment_intent_id", "payments", ["stripe_payment_intent_id"])

    op.create_table(
        "payment_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("provider_tx_id", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payment_transactions_payment_id", "payment_transactions", ["payment_id"])
    op.create_index("ix_payment_transactions_order_id", "payment_transactions", ["order_id"])
    op.create_index("ix_payment_transactions_status", "payment_transactions", ["status"])
    op.create_index("ix_payment_transactions_payment", "payment_transactions", ["payment_id"])
    op.create_index("ix_payment_transactions_order", "payment_transactions", ["order_id"])
    op.create_index("ix_payment_transactions_provider_tx", "payment_transactions", ["provider", "provider_tx_id"])

    op.create_table(
        "stripe_checkout_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_session_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("payment_status", sa.String(length=50), nullable=True),
        sa.Column("checkout_url", sa.Text(), nullable=True),
        sa.Column("amount_total_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stripe_checkout_sessions_payment_id", "stripe_checkout_sessions", ["payment_id"])
    op.create_index("ix_stripe_checkout_sessions_order_id", "stripe_checkout_sessions", ["order_id"])
    op.create_index("ix_stripe_checkout_sessions_user_id", "stripe_checkout_sessions", ["user_id"])
    op.create_index("ix_stripe_checkout_sessions_status", "stripe_checkout_sessions", ["status"])
    op.create_index("ix_stripe_checkout_sessions_payment_status", "stripe_checkout_sessions", ["payment_status"])
    op.create_index("ix_stripe_checkout_sessions_payment", "stripe_checkout_sessions", ["payment_id"])
    op.create_index("ix_stripe_checkout_sessions_order", "stripe_checkout_sessions", ["order_id"])
    op.create_index("ix_stripe_checkout_sessions_provider_session_id", "stripe_checkout_sessions", ["provider_session_id"], unique=True)

    op.create_table(
        "stripe_payment_intents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_payment_intent_id", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("latest_charge_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("succeeded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stripe_payment_intents_payment_id", "stripe_payment_intents", ["payment_id"])
    op.create_index("ix_stripe_payment_intents_order_id", "stripe_payment_intents", ["order_id"])
    op.create_index("ix_stripe_payment_intents_status", "stripe_payment_intents", ["status"])
    op.create_index("ix_stripe_payment_intents_payment", "stripe_payment_intents", ["payment_id"])
    op.create_index("ix_stripe_payment_intents_order", "stripe_payment_intents", ["order_id"])
    op.create_index("ix_stripe_payment_intents_provider_payment_intent_id", "stripe_payment_intents", ["provider_payment_intent_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_stripe_payment_intents_provider_payment_intent_id", table_name="stripe_payment_intents")
    op.drop_index("ix_stripe_payment_intents_order", table_name="stripe_payment_intents")
    op.drop_index("ix_stripe_payment_intents_payment", table_name="stripe_payment_intents")
    op.drop_index("ix_stripe_payment_intents_status", table_name="stripe_payment_intents")
    op.drop_index("ix_stripe_payment_intents_order_id", table_name="stripe_payment_intents")
    op.drop_index("ix_stripe_payment_intents_payment_id", table_name="stripe_payment_intents")
    op.drop_table("stripe_payment_intents")

    op.drop_index("ix_stripe_checkout_sessions_provider_session_id", table_name="stripe_checkout_sessions")
    op.drop_index("ix_stripe_checkout_sessions_order", table_name="stripe_checkout_sessions")
    op.drop_index("ix_stripe_checkout_sessions_payment", table_name="stripe_checkout_sessions")
    op.drop_index("ix_stripe_checkout_sessions_payment_status", table_name="stripe_checkout_sessions")
    op.drop_index("ix_stripe_checkout_sessions_status", table_name="stripe_checkout_sessions")
    op.drop_index("ix_stripe_checkout_sessions_user_id", table_name="stripe_checkout_sessions")
    op.drop_index("ix_stripe_checkout_sessions_order_id", table_name="stripe_checkout_sessions")
    op.drop_index("ix_stripe_checkout_sessions_payment_id", table_name="stripe_checkout_sessions")
    op.drop_table("stripe_checkout_sessions")

    op.drop_index("ix_payment_transactions_provider_tx", table_name="payment_transactions")
    op.drop_index("ix_payment_transactions_order", table_name="payment_transactions")
    op.drop_index("ix_payment_transactions_payment", table_name="payment_transactions")
    op.drop_index("ix_payment_transactions_status", table_name="payment_transactions")
    op.drop_index("ix_payment_transactions_order_id", table_name="payment_transactions")
    op.drop_index("ix_payment_transactions_payment_id", table_name="payment_transactions")
    op.drop_table("payment_transactions")

    op.drop_index("ix_payments_stripe_payment_intent_id", table_name="payments")
    op.drop_index("ix_payments_stripe_checkout_session_id", table_name="payments")
    op.drop_index("ix_payments_user_status", table_name="payments")
    op.drop_index("ix_payments_order_status", table_name="payments")
    op.drop_index("ix_payments_status", table_name="payments")
    op.drop_index("ix_payments_payer_user_id", table_name="payments")
    op.drop_index("ix_payments_order_id", table_name="payments")
    op.drop_table("payments")
