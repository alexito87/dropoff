from typing import Any

from sqlalchemy.orm import Session

from app.events.handlers.base import (
    EventHandlingResult,
    log_event_received,
    processed,
    require_data_fields,
    require_event_fields,
)


def handle_delivery_created(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "delivery_id", "order_id", "order_item_id", "item_id", "status")

    log_event_received(
        db=db,
        handler_name="handle_delivery_created",
        event=event,
    )

    return processed(
        "Delivery created event accepted for future orders/notifications projection",
        target_contexts=["orders", "notifications", "audit"],
    )


def handle_delivery_completed(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "delivery_id", "order_id", "order_item_id", "item_id", "status")

    log_event_received(
        db=db,
        handler_name="handle_delivery_completed",
        event=event,
    )

    return processed(
        "Delivery completed event accepted for future orders/notifications projection",
        target_contexts=["orders", "notifications", "audit"],
    )


def handle_delivery_return_requested(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "delivery_id", "order_id", "order_item_id", "item_id", "status")

    log_event_received(
        db=db,
        handler_name="handle_delivery_return_requested",
        event=event,
    )

    return processed(
        "Delivery return requested event accepted for future orders/notifications projection",
        target_contexts=["orders", "notifications", "audit"],
    )


def handle_delivery_cancelled(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "delivery_id", "order_id", "order_item_id", "item_id", "status")

    log_event_received(
        db=db,
        handler_name="handle_delivery_cancelled",
        event=event,
    )

    return processed(
        "Delivery cancelled event accepted for future orders/notifications projection",
        target_contexts=["orders", "notifications", "audit"],
    )