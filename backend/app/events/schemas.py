from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EventEnvelope(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    event_type: str
    event_version: int = 1
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    producer: str = "dropoff-backend"
    correlation_id: str | None = None
    aggregate_type: str
    aggregate_id: str
    data: dict[str, Any] = Field(default_factory=dict)

    def to_kafka_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")