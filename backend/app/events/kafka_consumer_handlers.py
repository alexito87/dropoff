import logging
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.consumed_kafka_event import ConsumedKafkaEvent

logger = logging.getLogger(__name__)


def _extract_event_id(payload: dict[str, Any]) -> str | None:
    event_id = payload.get("event_id")
    return str(event_id) if event_id else None


def _extract_event_type(payload: dict[str, Any]) -> str:
    event_type = payload.get("event_type")
    return str(event_type) if event_type else "unknown"


def _extract_aggregate_type(payload: dict[str, Any]) -> str | None:
    aggregate_type = payload.get("aggregate_type")
    return str(aggregate_type) if aggregate_type else None


def _extract_aggregate_id(payload: dict[str, Any]) -> str | None:
    aggregate_id = payload.get("aggregate_id")
    return str(aggregate_id) if aggregate_id else None


def record_consumed_kafka_event(
    db: Session,
    *,
    consumer_name: str,
    topic: str,
    partition: int,
    offset: int,
    event_key: str | None,
    payload: dict[str, Any],
    status: str = "processed",
    error_message: str | None = None,
) -> ConsumedKafkaEvent | None:
    consumed_event = ConsumedKafkaEvent(
        consumer_name=consumer_name,
        topic=topic,
        partition=partition,
        offset=offset,
        event_type=_extract_event_type(payload),
        event_id=_extract_event_id(payload),
        event_key=event_key,
        aggregate_type=_extract_aggregate_type(payload),
        aggregate_id=_extract_aggregate_id(payload),
        payload=payload,
        status=status,
        error_message=error_message,
    )

    db.add(consumed_event)

    try:
        db.commit()
        db.refresh(consumed_event)
        return consumed_event
    except IntegrityError:
        db.rollback()
        logger.info(
            "Kafka event already consumed: consumer=%s topic=%s partition=%s offset=%s",
            consumer_name,
            topic,
            partition,
            offset,
        )
        return None
    except Exception:
        db.rollback()
        raise