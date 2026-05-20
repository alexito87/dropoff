from typing import Any

from sqlalchemy.orm import Session

from app.events.handlers.base import (
    EventHandlingResult,
    log_event_received,
    processed,
    require_data_fields,
    require_event_fields,
)


def handle_user_created(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "user_id", "email")

    log_event_received(
        db=db,
        handler_name="handle_user_created",
        event=event,
    )

    return processed(
        "User created event accepted for future target-context projection",
        target_contexts=["notifications", "orders", "audit"],
    )


def handle_user_email_verified(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "user_id", "email", "email_verified")

    log_event_received(
        db=db,
        handler_name="handle_user_email_verified",
        event=event,
    )

    return processed(
        "User email verified event accepted for future target-context projection",
        target_contexts=["notifications", "audit"],
    )