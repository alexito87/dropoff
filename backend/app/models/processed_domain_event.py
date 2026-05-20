import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ProcessedDomainEvent(Base):
    __tablename__ = "processed_domain_events"
    __table_args__ = (
        UniqueConstraint(
            "consumer_name",
            "event_id",
            name="uq_processed_domain_events_consumer_event_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    consumer_name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)

    event_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(150), nullable=False, index=True)

    topic: Mapped[str] = mapped_column(String(200), nullable=False, index=True)

    aggregate_type: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    aggregate_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    handling_status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    handling_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)

    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )