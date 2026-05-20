from typing import Any

from sqlalchemy.orm import Session

from app.events.handlers.base import (
    EventHandlingResult,
    log_event_received,
    processed,
    require_data_fields,
    require_event_fields,
)


def handle_item_created(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "item_id", "owner_id", "category_id", "title", "status")

    log_event_received(
        db=db,
        handler_name="handle_item_created",
        event=event,
    )

    return processed(
        "Item created event accepted for future catalog/orders projection",
        target_contexts=["catalog", "orders", "audit"],
    )


def handle_item_updated(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "item_id", "owner_id", "category_id", "title", "status")

    log_event_received(
        db=db,
        handler_name="handle_item_updated",
        event=event,
    )

    return processed(
        "Item updated event accepted for future catalog/orders projection",
        target_contexts=["catalog", "orders", "audit"],
    )


def handle_item_deleted(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "item_id", "owner_id")

    log_event_received(
        db=db,
        handler_name="handle_item_deleted",
        event=event,
    )

    return processed(
        "Item deleted event accepted for future catalog/orders projection",
        target_contexts=["catalog", "orders", "audit"],
    )


def handle_item_submitted_for_moderation(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "item_id", "owner_id", "status")

    log_event_received(
        db=db,
        handler_name="handle_item_submitted_for_moderation",
        event=event,
    )

    return processed(
        "Item submitted for moderation event accepted",
        target_contexts=["moderation", "audit"],
    )


def handle_item_published(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "item_id", "owner_id", "status")

    log_event_received(
        db=db,
        handler_name="handle_item_published",
        event=event,
    )

    return processed(
        "Item published event accepted for future catalog projection",
        target_contexts=["catalog", "notifications", "audit"],
    )


def handle_item_rejected(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "item_id", "owner_id", "status")

    log_event_received(
        db=db,
        handler_name="handle_item_rejected",
        event=event,
    )

    return processed(
        "Item rejected event accepted for future notification/audit projection",
        target_contexts=["notifications", "audit"],
    )