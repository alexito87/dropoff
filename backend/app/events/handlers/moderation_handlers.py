from typing import Any

from sqlalchemy.orm import Session

from app.events.business_processes import apply_moderation_event_to_item
from app.events.handlers.base import (
    EventHandlingResult,
    log_event_received,
    processed,
    require_data_fields,
    require_event_fields,
)
from app.events.projection_utils import (
    apply_values,
    get_event_data,
    get_or_create_projection,
    source_fields,
)
from app.models.event_projection import ModerationItemProjection


def _upsert_moderation_item_projection(db: Session, event: dict[str, Any]) -> None:
    data = get_event_data(event)
    item_id = str(data["item_id"])

    projection = get_or_create_projection(
        db,
        ModerationItemProjection,
        lookup_field="item_id",
        lookup_value=item_id,
    )

    apply_values(
        projection,
        {
            "owner_id": data.get("owner_id"),
            "category_id": data.get("category_id"),
            "title": data.get("title"),
            "item_status": data.get("target_status") or data.get("status"),
            "moderation_status": data.get("decision"),
            "moderation_comment": data.get("moderation_comment"),
            **source_fields(event),
        },
    )


def handle_moderation_item_approved(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "item_id", "decision", "target_status", "moderator_user_id")

    log_event_received(db=db, handler_name="handle_moderation_item_approved", event=event)

    _upsert_moderation_item_projection(db, event)

    business_result = apply_moderation_event_to_item(db, event)

    return processed(
        "Moderation approved event projected and applied to item",
        target_contexts=["moderation", "items", "notifications"],
        business_result=business_result,
    )


def handle_moderation_item_rejected(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "item_id", "decision", "target_status", "moderator_user_id")

    log_event_received(db=db, handler_name="handle_moderation_item_rejected", event=event)

    _upsert_moderation_item_projection(db, event)

    business_result = apply_moderation_event_to_item(db, event)

    return processed(
        "Moderation rejected event projected and applied to item",
        target_contexts=["moderation", "items", "notifications"],
        business_result=business_result,
    )


def handle_moderation_item_needs_changes(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "item_id", "decision", "target_status", "moderator_user_id")

    log_event_received(db=db, handler_name="handle_moderation_item_needs_changes", event=event)

    _upsert_moderation_item_projection(db, event)

    business_result = apply_moderation_event_to_item(db, event)

    return processed(
        "Moderation needs changes event projected and applied to item",
        target_contexts=["moderation", "items", "notifications"],
        business_result=business_result,
    )