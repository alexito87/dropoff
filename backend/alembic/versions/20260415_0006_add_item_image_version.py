"""add item image version

Revision ID: 20260415_0006
Revises: 0007_add_rental_indexes
Create Date: 2026-04-15 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260415_0006"
down_revision: Union[str, None] = "0007_add_rental_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "item_images",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("item_images", "version")