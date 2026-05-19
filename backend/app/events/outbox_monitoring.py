from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.outbox_event import OutboxEvent


def get_outbox_summary(db: Session) -> dict:
    rows = (
        db.query(
            OutboxEvent.status,
            OutboxEvent.topic,
            func.count(OutboxEvent.id),
        )
        .group_by(OutboxEvent.status, OutboxEvent.topic)
        .order_by(OutboxEvent.topic.asc(), OutboxEvent.status.asc())
        .all()
    )

    by_topic: dict[str, dict[str, int]] = {}
    totals = {
        "pending": 0,
        "published": 0,
        "failed": 0,
        "other": 0,
        "all": 0,
    }

    for status, topic, count in rows:
        count = int(count)
        by_topic.setdefault(
            topic,
            {
                "pending": 0,
                "published": 0,
                "failed": 0,
                "other": 0,
                "all": 0,
            },
        )

        if status in {"pending", "published", "failed"}:
            by_topic[topic][status] += count
            totals[status] += count
        else:
            by_topic[topic]["other"] += count
            totals["other"] += count

        by_topic[topic]["all"] += count
        totals["all"] += count

    return {
        "totals": totals,
        "topics": by_topic,
    }


def get_recent_outbox_events(
    db: Session,
    *,
    limit: int = 20,
    status: str | None = None,
    topic: str | None = None,
) -> list[dict]:
    query = db.query(OutboxEvent)

    if status:
        query = query.filter(OutboxEvent.status == status)

    if topic:
        query = query.filter(OutboxEvent.topic == topic)

    events = (
        query
        .order_by(OutboxEvent.created_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": str(event.id),
            "aggregate_type": event.aggregate_type,
            "aggregate_id": event.aggregate_id,
            "event_type": event.event_type,
            "event_version": event.event_version,
            "topic": event.topic,
            "event_key": event.event_key,
            "status": event.status,
            "retry_count": event.retry_count,
            "last_error": event.last_error,
            "created_at": event.created_at.isoformat() if event.created_at else None,
            "published_at": event.published_at.isoformat() if event.published_at else None,
        }
        for event in events
    ]