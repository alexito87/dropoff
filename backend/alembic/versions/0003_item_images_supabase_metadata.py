"""item images supabase metadata

Revision ID: 0003_item_images_supabase_metadata
Revises: 0002_email_verification_tokens
Create Date: 2026-04-07
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_item_images_meta"
down_revision = "0002_email_verification_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "item_images",
        sa.Column("storage_path", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "item_images",
        sa.Column("mime_type", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "item_images",
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
    )
    op.add_column(
        "item_images",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )

    op.execute("UPDATE item_images SET storage_path = '' WHERE storage_path IS NULL")
    op.execute("UPDATE item_images SET mime_type = 'image/jpeg' WHERE mime_type IS NULL")
    op.execute("UPDATE item_images SET file_size_bytes = 0 WHERE file_size_bytes IS NULL")

    op.alter_column("item_images", "storage_path", nullable=False)
    op.alter_column("item_images", "mime_type", nullable=False)
    op.alter_column("item_images", "file_size_bytes", nullable=False)

    op.create_index(
        op.f("ix_item_images_item_id"),
        "item_images",
        ["item_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_item_images_item_id"), table_name="item_images")
    op.drop_column("item_images", "version")
    op.drop_column("item_images", "file_size_bytes")
    op.drop_column("item_images", "mime_type")
    op.drop_column("item_images", "storage_path")