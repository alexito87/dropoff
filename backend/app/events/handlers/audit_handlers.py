from typing import Any

from sqlalchemy.orm import Session

from app.events.handlers.base import (
    EventHandlingResult,
    log_event_received,
    processed,
    require_event_fields,
)


def handle_audit_domain_event_seeded(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")

    log_event_received(
        db=db,
        handler_name="handle_audit_domain_event_seeded",
        event=event,
    )

    return processed(
        "Audit domain event accepted",
        target_contexts=["audit"],
    )