import logging
from typing import Any

from sqlalchemy.orm import Session

from app.email.publisher import enqueue_notification_email
from app.events.handlers.base import (
    EventHandlingResult,
    failed,
    log_event_received,
    processed,
    require_data_fields,
    require_event_fields,
)
from app.events.projection_utils import get_event_data
from app.models.event_projection import AuditDomainEventProjection

logger = logging.getLogger(__name__)


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

    try:
        email_result = enqueue_notification_email(
            db,
            notification_id=str(data["notification_id"]),
            user_id=str(data["user_id"]),
            notification_type=str(data["type"]),
            payload=data.get("payload") or {},
            correlation_id=event.get("correlation_id"),
            causation_id=event.get("event_id"),
        )

    except Exception as exc:
        logger.exception(
            "Failed to publish notification email message to RabbitMQ: notification_id=%s event_id=%s",
            data.get("notification_id"),
            event.get("event_id"),
        )

        return failed(
            "Notification was projected, but email message was not published to RabbitMQ",
            target_contexts=["audit", "email"],
            notification_id=data.get("notification_id"),
            error_message=str(exc),
        )

    return processed(
        "Notification created event projected and email message queued",
        target_contexts=["audit", "email"],
        notification_id=data.get("notification_id"),
        email=email_result,
    )