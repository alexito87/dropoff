from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, get_db
from app.events.kafka_health import check_kafka_connection
from app.events.outbox_monitoring import (
    get_outbox_summary,
    get_recent_outbox_events,
)
from app.events.outbox_publisher import publish_pending_outbox_events
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


@router.post("/publish-outbox")
async def publish_outbox_events(
    limit: int = Query(default=10, ge=1, le=100),
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    publish_result = await publish_pending_outbox_events(db, limit=limit)

    return {
        "service": "outbox",
        "status": "processed",
        "result": publish_result,
    }