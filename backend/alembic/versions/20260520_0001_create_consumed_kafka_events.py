"""create consumed kafka events

Revision ID: 20260520_0001
Revises: 968855a3c99b
Create Date: 2026-05-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260520_0001"
down_revision: Union[str, None] = "968855a3c99b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "consumed_kafka_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consumer_name", sa.String(length=150), nullable=False),
        sa.Column("topic", sa.String(length=200), nullable=False),
        sa.Column("partition", sa.Integer(), nullable=False),
        sa.Column("offset", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=150), nullable=False),
        sa.Column("event_id", sa.String(length=100), nullable=True),
        sa.Column("event_key", sa.String(length=200), nullable=True),
        sa.Column("aggregate_type", sa.String(length=100), nullable=True),
        sa.Column("aggregate_id", sa.String(length=100), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "consumed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "consumer_name",
            "topic",
            "partition",
            "offset",
            name="uq_consumed_kafka_events_consumer_topic_partition_offset",
        ),
    )

    op.create_index(
        "ix_consumed_kafka_events_consumer_name",
        "consumed_kafka_events",
        ["consumer_name"],
    )
    op.create_index(
        "ix_consumed_kafka_events_topic",
        "consumed_kafka_events",
        ["topic"],
    )
    op.create_index(
        "ix_consumed_kafka_events_event_type",
        "consumed_kafka_events",
        ["event_type"],
    )
    op.create_index(
        "ix_consumed_kafka_events_event_id",
        "consumed_kafka_events",
        ["event_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_consumed_kafka_events_event_id", table_name="consumed_kafka_events")
    op.drop_index("ix_consumed_kafka_events_event_type", table_name="consumed_kafka_events")
    op.drop_index("ix_consumed_kafka_events_topic", table_name="consumed_kafka_events")
    op.drop_index("ix_consumed_kafka_events_consumer_name", table_name="consumed_kafka_events")
    op.drop_table("consumed_kafka_events")