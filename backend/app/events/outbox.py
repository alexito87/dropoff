from sqlalchemy.orm import Session

from app.events.schemas import EventEnvelope
from app.models.outbox_event import OutboxEvent


def add_event_to_outbox(
    db: Session,
    *,
    topic: str,
    event: EventEnvelope,
    key: str | None = None,
) -> OutboxEvent:
    """
    Добавляет доменное событие в transactional outbox.

    Важно:
    - эта функция НЕ делает db.commit();
    - вызывающий код сам решает, когда делать commit;
    - бизнес-изменения и outbox_event должны сохраняться в одной DB-транзакции.
    """
    outbox_event = OutboxEvent(
        aggregate_type=event.aggregate_type,
        aggregate_id=event.aggregate_id,
        event_type=event.event_type,
        event_version=event.event_version,
        topic=topic,
        event_key=key,
        payload=event.to_kafka_dict(),
        status="pending",
    )

    db.add(outbox_event)
    return outbox_event