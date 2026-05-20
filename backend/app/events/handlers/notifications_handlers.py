from typing import Any

from sqlalchemy.orm import Session

from app.events.handlers.base import (
    EventHandlingResult,
    log_event_received,
    processed,
    require_data_fields,
    require_event_fields,
)


def handle_notification_created(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "notification_id", "user_id", "type", "payload")

    log_event_received(
        db=db,
        handler_name="handle_notification_created",
        event=event,
    )

    return processed(
        "Notification created event accepted for future audit projection",
        target_contexts=["audit"],
    )