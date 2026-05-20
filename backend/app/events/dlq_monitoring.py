from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.dead_letter_kafka_event import DeadLetterKafkaEvent


def get_dead_letter_summary(db: Session) -> dict[str, Any]:
    rows = (
        db.query(
            DeadLetterKafkaEvent.topic,
            DeadLetterKafkaEvent.status,
            DeadLetterKafkaEvent.error_type,
            func.count(DeadLetterKafkaEvent.id),
        )
        .group_by(
            DeadLetterKafkaEvent.topic,
            DeadLetterKafkaEvent.status,
            DeadLetterKafkaEvent.error_type,
        )
        .order_by(
            DeadLetterKafkaEvent.topic.asc(),
            DeadLetterKafkaEvent.status.asc(),
            DeadLetterKafkaEvent.error_type.asc(),
        )
        .all()
    )

    totals = {
        "new": 0,
        "resolved": 0,
        "ignored": 0,
        "other": 0,
        "all": 0,
    }

    topics: dict[str, dict[str, Any]] = {}

    for topic, status, error_type, count in rows:
        count = int(count)
        bucket = status if status in {"new", "resolved", "ignored"} else "other"

        topics.setdefault(
            topic,
            {
                "statuses": {
                    "new": 0,
                    "resolved": 0,
                    "ignored": 0,
                    "other": 0,
                    "all": 0,
                },
                "error_types": {},
            },
        )

        topics[topic]["statuses"][bucket] += count
        topics[topic]["statuses"]["all"] += count
        topics[topic]["error_types"][error_type] = (
            topics[topic]["error_types"].get(error_type, 0) + count
        )

        totals[bucket] += count
        totals["all"] += count

    return {
        "totals": totals,
        "topics": topics,
    }


def get_recent_dead_letter_events(
    db: Session,
    *,
    limit: int = 20,
    topic: str | None = None,
    status: str | None = None,
    error_type: str | None = None,
    event_type: str | None = None,
) -> list[dict[str, Any]]:
    query = db.query(DeadLetterKafkaEvent)

    if topic:
        query = query.filter(DeadLetterKafkaEvent.topic == topic)

    if status:
        query = query.filter(DeadLetterKafkaEvent.status == status)

    if error_type:
        query = query.filter(DeadLetterKafkaEvent.error_type == error_type)

    if event_type:
        query = query.filter(DeadLetterKafkaEvent.event_type == event_type)

    events = (
        query
        .order_by(DeadLetterKafkaEvent.created_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": str(event.id),
            "consumer_name": event.consumer_name,
            "topic": event.topic,
            "partition": event.partition,
            "offset": event.offset,
            "event_key": event.event_key,
            "event_id": event.event_id,
            "event_type": event.event_type,
            "aggregate_type": event.aggregate_type,
            "aggregate_id": event.aggregate_id,
            "error_type": event.error_type,
            "error_message": event.error_message,
            "status": event.status,
            "created_at": event.created_at.isoformat() if event.created_at else None,
            "resolved_at": event.resolved_at.isoformat() if event.resolved_at else None,
        }
        for event in events
    ]