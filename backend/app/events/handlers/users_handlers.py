from typing import Any

from sqlalchemy.orm import Session

from app.events.handlers.base import (
    EventHandlingResult,
    log_event_received,
    processed,
    require_data_fields,
    require_event_fields,
)
from app.events.projection_utils import apply_values, get_event_data, get_or_create_projection, source_fields
from app.models.event_projection import NotificationsUserProjection


def _upsert_notifications_user_projection(db: Session, event: dict[str, Any]) -> None:
    data = get_event_data(event)
    user_id = str(data["user_id"])

    projection = get_or_create_projection(
        db,
        NotificationsUserProjection,
        lookup_field="user_id",
        lookup_value=user_id,
    )

    apply_values(
        projection,
        {
            "email": data.get("email"),
            "full_name": data.get("full_name"),
            "email_verified": data.get("email_verified"),
            "is_superuser": data.get("is_superuser"),
            **source_fields(event),
        },
    )


def handle_user_created(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "user_id", "email")

    log_event_received(
        db=db,
        handler_name="handle_user_created",
        event=event,
    )

    _upsert_notifications_user_projection(db, event)

    return processed(
        "User created event projected to notifications user projection",
        target_contexts=["notifications"],
    )


def handle_user_email_verified(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "user_id", "email", "email_verified")

    log_event_received(
        db=db,
        handler_name="handle_user_email_verified",
        event=event,
    )

    _upsert_notifications_user_projection(db, event)

    return processed(
        "User email verified event projected to notifications user projection",
        target_contexts=["notifications"],
    )