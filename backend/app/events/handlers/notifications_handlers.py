from typing import Any

from sqlalchemy.orm import Session

from app.events.handlers.base import (
    EventHandlingResult,
    log_event_received,
    processed,
    require_data_fields,
    require_event_fields,
)
from app.events.projection_utils import get_event_data
from app.models.event_projection import AuditDomainEventProjection


def handle_notification_created(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "notification_id", "user_id", "type", "payload")

    log_event_received(db=db, handler_name="handle_notification_created", event=event)

    data = get_event_data(event)

    existing = (
        db.query(AuditDomainEventProjection)
        .filter(AuditDomainEventProjection.source_event_id == str(event["event_id"]))
        .first()
    )

    if not existing:
        db.add(
            AuditDomainEventProjection(
                source_event_id=str(event["event_id"]),
                source_event_type=str(event["event_type"]),
                producer=event.get("producer"),
                aggregate_type=event.get("aggregate_type"),
                aggregate_id=event.get("aggregate_id"),
                source_payload={
                    **event,
                    "notification_payload": data,
                },
            )
        )

    return processed(
        "Notification created event projected to audit domain event projection",
        target_contexts=["audit"],
    )