from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.events.producer import kafka_event_producer
from app.events.schemas import EventEnvelope
from app.models.outbox_event import OutboxEvent


def get_pending_outbox_events(
    db: Session,
    *,
    limit: int = 10,
) -> list[OutboxEvent]:
    return (
        db.query(OutboxEvent)
        .filter(OutboxEvent.status == "pending")
        .order_by(OutboxEvent.created_at.asc())
        .limit(limit)
        .all()
    )


async def publish_pending_outbox_events(
    db: Session,
    *,
    limit: int = 10,
) -> dict[str, Any]:
    pending_events = get_pending_outbox_events(db, limit=limit)

    result: dict[str, Any] = {
        "selected": len(pending_events),
        "published": 0,
        "failed": 0,
        "items": [],
    }

    for outbox_event in pending_events:
        try:
            event = EventEnvelope.model_validate(outbox_event.payload)

            publish_result = await kafka_event_producer.publish(
                topic=outbox_event.topic,
                event=event,
                key=outbox_event.event_key,
            )

            outbox_event.status = "published"
            outbox_event.published_at = datetime.now(UTC)
            outbox_event.last_error = None

            result["published"] += 1
            result["items"].append(
                {
                    "outbox_event_id": str(outbox_event.id),
                    "event_type": outbox_event.event_type,
                    "topic": outbox_event.topic,
                    "status": "published",
                    "kafka": publish_result,
                }
            )

        except Exception as exc:
            outbox_event.retry_count += 1
            outbox_event.last_error = str(exc)

            result["failed"] += 1
            result["items"].append(
                {
                    "outbox_event_id": str(outbox_event.id),
                    "event_type": outbox_event.event_type,
                    "topic": outbox_event.topic,
                    "status": "failed",
                    "error": str(exc),
                    "retry_count": outbox_event.retry_count,
                }
            )

        db.add(outbox_event)

    db.commit()

    return result