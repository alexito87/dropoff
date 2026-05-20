"""create processed domain events

Revision ID: 20260520_0003
Revises: 20260520_0002
Create Date: 2026-05-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260520_0003"
down_revision: Union[str, None] = "20260520_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "processed_domain_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consumer_name", sa.String(length=150), nullable=False),
        sa.Column("event_id", sa.String(length=100), nullable=False),
        sa.Column("event_type", sa.String(length=150), nullable=False),
        sa.Column("topic", sa.String(length=200), nullable=False),
        sa.Column("aggregate_type", sa.String(length=100), nullable=True),
        sa.Column("aggregate_id", sa.String(length=100), nullable=True),
        sa.Column("handling_status", sa.String(length=30), nullable=False),
        sa.Column("handling_message", sa.String(length=1000), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "consumer_name",
            "event_id",
            name="uq_processed_domain_events_consumer_event_id",
        ),
    )

    op.create_index(
        "ix_processed_domain_events_consumer_name",
        "processed_domain_events",
        ["consumer_name"],
    )
    op.create_index(
        "ix_processed_domain_events_event_id",
        "processed_domain_events",
        ["event_id"],
    )
    op.create_index(
        "ix_processed_domain_events_event_type",
        "processed_domain_events",
        ["event_type"],
    )
    op.create_index(
        "ix_processed_domain_events_topic",
        "processed_domain_events",
        ["topic"],
    )
    op.create_index(
        "ix_processed_domain_events_aggregate_type",
        "processed_domain_events",
        ["aggregate_type"],
    )
    op.create_index(
        "ix_processed_domain_events_aggregate_id",
        "processed_domain_events",
        ["aggregate_id"],
    )
    op.create_index(
        "ix_processed_domain_events_handling_status",
        "processed_domain_events",
        ["handling_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_processed_domain_events_handling_status", table_name="processed_domain_events")
    op.drop_index("ix_processed_domain_events_aggregate_id", table_name="processed_domain_events")
    op.drop_index("ix_processed_domain_events_aggregate_type", table_name="processed_domain_events")
    op.drop_index("ix_processed_domain_events_topic", table_name="processed_domain_events")
    op.drop_index("ix_processed_domain_events_event_type", table_name="processed_domain_events")
    op.drop_index("ix_processed_domain_events_event_id", table_name="processed_domain_events")
    op.drop_index("ix_processed_domain_events_consumer_name", table_name="processed_domain_events")
    op.drop_table("processed_domain_events")