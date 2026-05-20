from typing import Any

from sqlalchemy.orm import Session

from app.events.handlers.base import (
    EventHandlingResult,
    log_event_received,
    processed,
    require_data_fields,
    require_event_fields,
)


def handle_moderation_item_approved(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "item_id", "decision", "target_status", "moderator_user_id")

    log_event_received(
        db=db,
        handler_name="handle_moderation_item_approved",
        event=event,
    )

    return processed(
        "Moderation approved event accepted",
        target_contexts=["items", "notifications", "audit"],
    )


def handle_moderation_item_rejected(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "item_id", "decision", "target_status", "moderator_user_id")

    log_event_received(
        db=db,
        handler_name="handle_moderation_item_rejected",
        event=event,
    )

    return processed(
        "Moderation rejected event accepted",
        target_contexts=["items", "notifications", "audit"],
    )


def handle_moderation_item_needs_changes(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "item_id", "decision", "target_status", "moderator_user_id")

    log_event_received(
        db=db,
        handler_name="handle_moderation_item_needs_changes",
        event=event,
    )

    return processed(
        "Moderation needs changes event accepted",
        target_contexts=["items", "notifications", "audit"],
    )