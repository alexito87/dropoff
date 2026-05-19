from sqlalchemy.orm import Session

from app.events.outbox import add_event_to_outbox
from app.events.schemas import EventEnvelope
from app.events.topics import USER_EVENTS_TOPIC


def _user_payload(user) -> dict:
    return {
        "user_id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "email_verified": user.email_verified,
        "is_superuser": user.is_superuser,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


def add_user_created_event_to_outbox(
    db: Session,
    *,
    user,
) -> None:
    event = EventEnvelope(
        event_type="user.created",
        producer="auth-endpoint",
        aggregate_type="User",
        aggregate_id=str(user.id),
        data=_user_payload(user),
    )

    add_event_to_outbox(
        db,
        topic=USER_EVENTS_TOPIC,
        event=event,
        key=str(user.id),
    )


def add_user_email_verified_event_to_outbox(
    db: Session,
    *,
    user,
) -> None:
    event = EventEnvelope(
        event_type="user.email_verified",
        producer="auth-endpoint",
        aggregate_type="User",
        aggregate_id=str(user.id),
        data=_user_payload(user),
    )

    add_event_to_outbox(
        db,
        topic=USER_EVENTS_TOPIC,
        event=event,
        key=str(user.id),
    )