""""fix items timestamp defaults

Revision ID: 0004_fix_items_timestamps_defaults
Revises: 0003_item_images_supabase_metadata
Create Date: 2026-04-08
"""

from alembic import op


revision = "0004_fix_items_ts"
down_revision = "0003_item_images_meta"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE items
        ALTER COLUMN created_at SET DEFAULT now(),
        ALTER COLUMN updated_at SET DEFAULT now()
        """
    )

    op.execute(
        """
        UPDATE items
        SET created_at = now()
        WHERE created_at IS NULL
        """
    )

    op.execute(
        """
        UPDATE items
        SET updated_at = now()
        WHERE updated_at IS NULL
        """
    )

    op.execute(
        """
        ALTER TABLE items
        ALTER COLUMN created_at SET NOT NULL,
        ALTER COLUMN updated_at SET NOT NULL
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE items
        ALTER COLUMN created_at DROP DEFAULT,
        ALTER COLUMN updated_at DROP DEFAULT
        """
    )