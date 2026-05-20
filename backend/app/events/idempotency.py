from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.events.handlers.base import EventHandlingResult
from app.models.processed_domain_event import ProcessedDomainEvent


IDEMPOTENT_STATUSES = {
    "processed",
    "ignored",
}


def get_event_id(event: dict[str, Any]) -> str | None:
    event_id = event.get("event_id")

    if event_id in (None, ""):
        return None

    return str(event_id)


def is_event_already_processed(
    db: Session,
    *,
    consumer_name: str,
    event: dict[str, Any],
) -> bool:
    event_id = get_event_id(event)

    if not event_id:
        return False

    existing = (
        db.query(ProcessedDomainEvent)
        .filter(
            ProcessedDomainEvent.consumer_name == consumer_name,
            ProcessedDomainEvent.event_id == event_id,
        )
        .first()
    )

    return existing is not None


def mark_event_processed(
    db: Session,
    *,
    consumer_name: str,
    topic: str,
    event: dict[str, Any],
    handling_result: EventHandlingResult,
) -> ProcessedDomainEvent | None:
    event_id = get_event_id(event)

    if not event_id:
        return None

    if handling_result.status not in IDEMPOTENT_STATUSES:
        return None

    processed_event = ProcessedDomainEvent(
        consumer_name=consumer_name,
        event_id=event_id,
        event_type=str(event.get("event_type") or "unknown"),
        topic=topic,
        aggregate_type=(
            str(event.get("aggregate_type"))
            if event.get("aggregate_type") not in (None, "")
            else None
        ),
        aggregate_id=(
            str(event.get("aggregate_id"))
            if event.get("aggregate_id") not in (None, "")
            else None
        ),
        handling_status=handling_result.status,
        handling_message=handling_result.message,
        payload=event,
    )

    db.add(processed_event)

    try:
        db.flush()
        return processed_event
    except IntegrityError:
        db.rollback()
        return None