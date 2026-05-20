"""create dead letter kafka events

Revision ID: 20260520_0004
Revises: 20260520_0003
Create Date: 2026-05-20
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260520_0004"
down_revision: Union[str, None] = "20260520_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dead_letter_kafka_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consumer_name", sa.String(length=150), nullable=False),
        sa.Column("topic", sa.String(length=200), nullable=False),
        sa.Column("partition", sa.Integer(), nullable=False),
        sa.Column("offset", sa.Integer(), nullable=False),
        sa.Column("event_key", sa.String(length=200), nullable=True),
        sa.Column("event_id", sa.String(length=100), nullable=True),
        sa.Column("event_type", sa.String(length=150), nullable=False),
        sa.Column("aggregate_type", sa.String(length=100), nullable=True),
        sa.Column("aggregate_id", sa.String(length=100), nullable=True),
        sa.Column("error_type", sa.String(length=100), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "consumer_name",
            "topic",
            "partition",
            "offset",
            name="uq_dead_letter_kafka_events_consumer_topic_partition_offset",
        ),
    )

    op.create_index(
        "ix_dead_letter_kafka_events_consumer_name",
        "dead_letter_kafka_events",
        ["consumer_name"],
    )
    op.create_index(
        "ix_dead_letter_kafka_events_topic",
        "dead_letter_kafka_events",
        ["topic"],
    )
    op.create_index(
        "ix_dead_letter_kafka_events_event_id",
        "dead_letter_kafka_events",
        ["event_id"],
    )
    op.create_index(
        "ix_dead_letter_kafka_events_event_type",
        "dead_letter_kafka_events",
        ["event_type"],
    )
    op.create_index(
        "ix_dead_letter_kafka_events_aggregate_type",
        "dead_letter_kafka_events",
        ["aggregate_type"],
    )
    op.create_index(
        "ix_dead_letter_kafka_events_aggregate_id",
        "dead_letter_kafka_events",
        ["aggregate_id"],
    )
    op.create_index(
        "ix_dead_letter_kafka_events_error_type",
        "dead_letter_kafka_events",
        ["error_type"],
    )
    op.create_index(
        "ix_dead_letter_kafka_events_status",
        "dead_letter_kafka_events",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_dead_letter_kafka_events_status", table_name="dead_letter_kafka_events")
    op.drop_index("ix_dead_letter_kafka_events_error_type", table_name="dead_letter_kafka_events")
    op.drop_index("ix_dead_letter_kafka_events_aggregate_id", table_name="dead_letter_kafka_events")
    op.drop_index("ix_dead_letter_kafka_events_aggregate_type", table_name="dead_letter_kafka_events")
    op.drop_index("ix_dead_letter_kafka_events_event_type", table_name="dead_letter_kafka_events")
    op.drop_index("ix_dead_letter_kafka_events_event_id", table_name="dead_letter_kafka_events")
    op.drop_index("ix_dead_letter_kafka_events_topic", table_name="dead_letter_kafka_events")
    op.drop_index("ix_dead_letter_kafka_events_consumer_name", table_name="dead_letter_kafka_events")
    op.drop_table("dead_letter_kafka_events")