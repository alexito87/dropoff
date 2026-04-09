"""add rental indexes

Revision ID: 0007_add_rental_indexes
Revises: 80c9576401f9
Create Date: 2026-04-09 16:00:00.000000
"""
from alembic import op

revision = "0007_add_rental_indexes"
down_revision = "80c9576401f9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_rentals_item_id", "rentals", ["item_id"], unique=False)
    op.create_index("ix_rentals_renter_id", "rentals", ["renter_id"], unique=False)
    op.create_index("ix_rentals_status", "rentals", ["status"], unique=False)
    op.create_index("ix_rentals_created_at", "rentals", ["created_at"], unique=False)
    op.create_index(
        "ix_rentals_item_status_dates",
        "rentals",
        ["item_id", "status", "start_date", "end_date"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_rentals_item_status_dates", table_name="rentals")
    op.drop_index("ix_rentals_created_at", table_name="rentals")
    op.drop_index("ix_rentals_status", table_name="rentals")
    op.drop_index("ix_rentals_renter_id", table_name="rentals")
    op.drop_index("ix_rentals_item_id", table_name="rentals")