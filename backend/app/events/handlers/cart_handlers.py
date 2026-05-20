from typing import Any

from sqlalchemy.orm import Session

from app.events.handlers.base import (
    EventHandlingResult,
    log_event_received,
    processed,
    require_data_fields,
    require_event_fields,
)


def handle_cart_item_added(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "cart_id", "user_id", "item")

    log_event_received(
        db=db,
        handler_name="handle_cart_item_added",
        event=event,
    )

    return processed(
        "Cart item added event accepted",
        target_contexts=["orders", "audit"],
    )


def handle_cart_item_removed(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "cart_id", "user_id", "item")

    log_event_received(
        db=db,
        handler_name="handle_cart_item_removed",
        event=event,
    )

    return processed(
        "Cart item removed event accepted",
        target_contexts=["orders", "audit"],
    )


def handle_cart_cleared(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "cart_id", "user_id", "items_count")

    log_event_received(
        db=db,
        handler_name="handle_cart_cleared",
        event=event,
    )

    return processed(
        "Cart cleared event accepted",
        target_contexts=["orders", "audit"],
    )


def handle_cart_converted_to_order(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "cart_id", "user_id", "order_id", "order_status", "total_amount_cents")

    log_event_received(
        db=db,
        handler_name="handle_cart_converted_to_order",
        event=event,
    )

    return processed(
        "Cart converted to order event accepted",
        target_contexts=["orders", "payments", "audit"],
    )