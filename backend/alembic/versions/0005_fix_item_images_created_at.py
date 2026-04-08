"""fix item_images created_at default"""

from alembic import op


revision = "0005_fix_item_images_created_at"
down_revision = "0004_fix_items_ts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE item_images
        SET created_at = NOW()
        WHERE created_at IS NULL
        """
    )

    op.execute(
        """
        ALTER TABLE item_images
        ALTER COLUMN created_at SET DEFAULT NOW()
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE item_images
        ALTER COLUMN created_at DROP DEFAULT
        """
    )