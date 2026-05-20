import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ConsumedKafkaEvent(Base):
    __tablename__ = "consumed_kafka_events"
    __table_args__ = (
        UniqueConstraint(
            "consumer_name",
            "topic",
            "partition",
            "offset",
            name="uq_consumed_kafka_events_consumer_topic_partition_offset",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    consumer_name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)

    topic: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    partition: Mapped[int] = mapped_column(Integer, nullable=False)
    offset: Mapped[int] = mapped_column(Integer, nullable=False)

    event_type: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    event_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    event_key: Mapped[str | None] = mapped_column(String(200), nullable=True)

    aggregate_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    aggregate_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    status: Mapped[str] = mapped_column(String(30), nullable=False, default="processed")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    consumed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )