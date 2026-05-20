from typing import Any

from sqlalchemy.orm import Session

from app.events.handlers.base import (
    EventHandlingResult,
    log_event_received,
    processed,
    require_event_fields,
)
from app.events.projection_utils import parse_event_datetime
from app.models.event_projection import AuditDomainEventProjection


def handle_audit_domain_event_seeded(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")

    log_event_received(db=db, handler_name="handle_audit_domain_event_seeded", event=event)

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
                source_payload=event,
                occurred_at=parse_event_datetime(event.get("occurred_at")),
            )
        )

    return processed(
        "Audit domain event projected to audit domain event projection",
        target_contexts=["audit"],
    )