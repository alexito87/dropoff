from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.consumed_kafka_event import ConsumedKafkaEvent


def get_consumed_events_summary(db: Session) -> dict:
    rows = (
        db.query(
            ConsumedKafkaEvent.consumer_name,
            ConsumedKafkaEvent.topic,
            ConsumedKafkaEvent.status,
            func.count(ConsumedKafkaEvent.id),
        )
        .group_by(
            ConsumedKafkaEvent.consumer_name,
            ConsumedKafkaEvent.topic,
            ConsumedKafkaEvent.status,
        )
        .order_by(
            ConsumedKafkaEvent.consumer_name.asc(),
            ConsumedKafkaEvent.topic.asc(),
            ConsumedKafkaEvent.status.asc(),
        )
        .all()
    )

    totals = {
        "processed": 0,
        "failed": 0,
        "other": 0,
        "all": 0,
    }

    consumers: dict[str, dict] = {}

    for consumer_name, topic, status, count in rows:
        count = int(count)

        consumers.setdefault(
            consumer_name,
            {
                "topics": {},
                "totals": {
                    "processed": 0,
                    "failed": 0,
                    "other": 0,
                    "all": 0,
                },
            },
        )

        consumers[consumer_name]["topics"].setdefault(
            topic,
            {
                "processed": 0,
                "failed": 0,
                "other": 0,
                "all": 0,
            },
        )

        bucket = status if status in {"processed", "failed"} else "other"

        consumers[consumer_name]["topics"][topic][bucket] += count
        consumers[consumer_name]["topics"][topic]["all"] += count

        consumers[consumer_name]["totals"][bucket] += count
        consumers[consumer_name]["totals"]["all"] += count

        totals[bucket] += count
        totals["all"] += count

    return {
        "totals": totals,
        "consumers": consumers,
    }


def get_recent_consumed_events(
    db: Session,
    *,
    limit: int = 20,
    consumer_name: str | None = None,
    topic: str | None = None,
    status: str | None = None,
) -> list[dict]:
    query = db.query(ConsumedKafkaEvent)

    if consumer_name:
        query = query.filter(ConsumedKafkaEvent.consumer_name == consumer_name)

    if topic:
        query = query.filter(ConsumedKafkaEvent.topic == topic)

    if status:
        query = query.filter(ConsumedKafkaEvent.status == status)

    events = (
        query
        .order_by(ConsumedKafkaEvent.consumed_at.desc())
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
            "event_type": event.event_type,
            "event_id": event.event_id,
            "event_key": event.event_key,
            "aggregate_type": event.aggregate_type,
            "aggregate_id": event.aggregate_id,
            "status": event.status,
            "error_message": event.error_message,
            "consumed_at": event.consumed_at.isoformat() if event.consumed_at else None,
        }
        for event in events
    ]