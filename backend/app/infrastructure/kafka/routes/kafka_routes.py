from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, get_db
from app.events.consumer_monitoring import (
    get_consumed_events_summary,
    get_recent_consumed_events,
)
from app.events.consumer_registry import KAFKA_CONSUMERS
from app.events.dlq_monitoring import (
    get_dead_letter_summary,
    get_recent_dead_letter_events,
)
from app.events.kafka_health import check_kafka_connection
from app.events.outbox_monitoring import (
    get_outbox_summary,
    get_recent_outbox_events,
)
from app.events.outbox_publisher import publish_pending_outbox_events
from app.events.projection_monitoring import (
    get_available_projection_tables,
    get_projection_summary,
    get_recent_projection_events,
)
from app.events.topics import ALL_TOPICS
from app.modules.users.models.user import User

router = APIRouter()


@router.get("/health")
async def kafka_health():
    health = await check_kafka_connection()

    return {
        "service": "kafka",
        **health,
        "planned_topics": ALL_TOPICS,
        "planned_consumers": [
            {
                "name": consumer.name,
                "topic": consumer.topic,
            }
            for consumer in KAFKA_CONSUMERS
        ],
    }


@router.get("/outbox/summary")
def read_outbox_summary(
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return {
        "service": "outbox",
        "summary": get_outbox_summary(db),
    }


@router.get("/outbox/events")
def read_recent_outbox_events(
    limit: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    topic: str | None = Query(default=None),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return {
        "service": "outbox",
        "events": get_recent_outbox_events(
            db,
            limit=limit,
            status=status,
            topic=topic,
        ),
    }


@router.get("/consumers/summary")
def read_consumers_summary(
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return {
        "service": "kafka-consumers",
        "planned_consumers": [
            {
                "name": consumer.name,
                "topic": consumer.topic,
            }
            for consumer in KAFKA_CONSUMERS
        ],
        "summary": get_consumed_events_summary(db),
    }


@router.get("/consumers/events")
def read_recent_consumed_events(
    limit: int = Query(default=20, ge=1, le=100),
    consumer_name: str | None = Query(default=None),
    topic: str | None = Query(default=None),
    status: str | None = Query(default=None),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return {
        "service": "kafka-consumers",
        "events": get_recent_consumed_events(
            db,
            limit=limit,
            consumer_name=consumer_name,
            topic=topic,
            status=status,
        ),
    }


@router.get("/projections/summary")
def read_projection_summary(
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return {
        "service": "kafka-projections",
        "summary": get_projection_summary(db),
        "available_tables": get_available_projection_tables(),
    }


@router.get("/projections/events")
def read_recent_projection_events(
    limit: int = Query(default=20, ge=1, le=100),
    table_name: str | None = Query(default=None),
    source_event_type: str | None = Query(default=None),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return {
        "service": "kafka-projections",
        "result": get_recent_projection_events(
            db,
            table_name=table_name,
            source_event_type=source_event_type,
            limit=limit,
        ),
    }


@router.get("/dlq/summary")
def read_dead_letter_summary(
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return {
        "service": "kafka-dlq",
        "summary": get_dead_letter_summary(db),
    }


@router.get("/dlq/events")
def read_recent_dead_letter_events(
    limit: int = Query(default=20, ge=1, le=100),
    topic: str | None = Query(default=None),
    status: str | None = Query(default=None),
    error_type: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return {
        "service": "kafka-dlq",
        "events": get_recent_dead_letter_events(
            db,
            limit=limit,
            topic=topic,
            status=status,
            error_type=error_type,
            event_type=event_type,
        ),
    }


@router.post("/publish-outbox")
async def publish_outbox_events(
    limit: int = Query(default=10, ge=1, le=100),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    publish_result = await publish_pending_outbox_events(db, limit=limit)

    return {
        "service": "outbox",
        "result": publish_result,
    }