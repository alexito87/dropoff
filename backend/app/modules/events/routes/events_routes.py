from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.events.event_dispatcher import list_registered_event_types
from app.models.outbox_event import OutboxEvent
from app.modules.users.models.user import User

router = APIRouter()


def _is_admin(user: User) -> bool:
    return bool(getattr(user, "is_superuser", False))


def _outbox_event_to_dict(event: OutboxEvent) -> dict:
    payload = event.payload or {}

    return {
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
        "payload": payload,
    }


@router.get("/registered-types")
def read_registered_event_types(
    current_user: User = Depends(get_current_user),
):
    if not _is_admin(current_user):
        return {
            "allowed": False,
            "reason": "Only admin can read registered event types",
            "event_types": [],
        }

    event_types = list_registered_event_types()

    return {
        "allowed": True,
        "count": len(event_types),
        "event_types": event_types,
    }


@router.get("/outbox/recent")
def read_recent_outbox_events(
    status: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    topic: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _is_admin(current_user):
        return {
            "allowed": False,
            "reason": "Only admin can read outbox events",
            "events": [],
        }

    query = db.query(OutboxEvent)

    if status:
        query = query.filter(OutboxEvent.status == status)

    if event_type:
        query = query.filter(OutboxEvent.event_type == event_type)

    if topic:
        query = query.filter(OutboxEvent.topic == topic)

    events = (
        query
        .order_by(OutboxEvent.created_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "allowed": True,
        "count": len(events),
        "events": [_outbox_event_to_dict(event) for event in events],
    }


@router.get("/outbox/by-aggregate/{aggregate_type}/{aggregate_id}")
def read_outbox_events_by_aggregate(
    aggregate_type: str,
    aggregate_id: str,
    limit: int = Query(default=100, ge=1, le=300),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _is_admin(current_user):
        return {
            "allowed": False,
            "reason": "Only admin can read outbox events",
            "events": [],
        }

    events = (
        db.query(OutboxEvent)
        .filter(
            OutboxEvent.aggregate_type == aggregate_type,
            OutboxEvent.aggregate_id == aggregate_id,
        )
        .order_by(OutboxEvent.created_at.asc())
        .limit(limit)
        .all()
    )

    return {
        "allowed": True,
        "aggregate_type": aggregate_type,
        "aggregate_id": aggregate_id,
        "count": len(events),
        "events": [_outbox_event_to_dict(event) for event in events],
    }


@router.get("/outbox/{event_id}")
def read_outbox_event(
    event_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not _is_admin(current_user):
        return {
            "allowed": False,
            "reason": "Only admin can read outbox events",
            "event": None,
        }

    event = db.query(OutboxEvent).filter(OutboxEvent.id == event_id).first()

    if not event:
        return {
            "allowed": True,
            "event": None,
        }

    return {
        "allowed": True,
        "event": _outbox_event_to_dict(event),
    }