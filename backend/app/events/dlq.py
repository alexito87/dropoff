import logging
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.dead_letter_kafka_event import DeadLetterKafkaEvent

logger = logging.getLogger(__name__)


def _safe_str(value: Any) -> str | None:
    if value in (None, ""):
        return None

    return str(value)


def record_dead_letter_event(
    db: Session,
    *,
    consumer_name: str,
    topic: str,
    partition: int,
    offset: int,
    event_key: str | None,
    payload: dict[str, Any],
    error_type: str,
    error_message: str,
) -> DeadLetterKafkaEvent | None:
    dead_letter_event = DeadLetterKafkaEvent(
        consumer_name=consumer_name,
        topic=topic,
        partition=partition,
        offset=offset,
        event_key=event_key,
        event_id=_safe_str(payload.get("event_id")),
        event_type=str(payload.get("event_type") or "unknown"),
        aggregate_type=_safe_str(payload.get("aggregate_type")),
        aggregate_id=_safe_str(payload.get("aggregate_id")),
        error_type=error_type,
        error_message=error_message,
        payload=payload,
        status="new",
    )

    db.add(dead_letter_event)

    try:
        db.flush()
        return dead_letter_event
    except IntegrityError:
        db.rollback()

        logger.info(
            "Dead letter Kafka event already recorded: consumer=%s topic=%s partition=%s offset=%s",
            consumer_name,
            topic,
            partition,
            offset,
        )

        return None