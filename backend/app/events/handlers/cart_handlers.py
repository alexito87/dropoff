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
from app.models.event_projection import OrdersCartProjection


def _upsert_orders_cart_projection(db: Session, event: dict[str, Any]) -> None:
    data = get_event_data(event)
    cart_id = str(data["cart_id"])

    projection = get_or_create_projection(
        db,
        OrdersCartProjection,
        lookup_field="cart_id",
        lookup_value=cart_id,
    )

    apply_values(
        projection,
        {
            "user_id": data.get("user_id"),
            "cart_status": data.get("status"),
            "last_order_id": data.get("order_id"),
            "last_order_status": data.get("order_status"),
            "items_count": data.get("items_count"),
            "total_amount_cents": data.get("total_amount_cents"),
            **source_fields(event),
        },
    )


def handle_cart_item_added(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "cart_id", "user_id", "item")

    log_event_received(db=db, handler_name="handle_cart_item_added", event=event)

    _upsert_orders_cart_projection(db, event)

    return processed(
        "Cart item added event projected to orders cart projection",
        target_contexts=["orders"],
    )


def handle_cart_item_removed(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "cart_id", "user_id", "item")

    log_event_received(db=db, handler_name="handle_cart_item_removed", event=event)

    _upsert_orders_cart_projection(db, event)

    return processed(
        "Cart item removed event projected to orders cart projection",
        target_contexts=["orders"],
    )


def handle_cart_cleared(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "cart_id", "user_id", "items_count")

    log_event_received(db=db, handler_name="handle_cart_cleared", event=event)

    _upsert_orders_cart_projection(db, event)

    return processed(
        "Cart cleared event projected to orders cart projection",
        target_contexts=["orders"],
    )


def handle_cart_converted_to_order(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "cart_id", "user_id", "order_id", "order_status", "total_amount_cents")

    log_event_received(db=db, handler_name="handle_cart_converted_to_order", event=event)

    _upsert_orders_cart_projection(db, event)

    return processed(
        "Cart converted to order event projected to orders cart projection",
        target_contexts=["orders"],
    )