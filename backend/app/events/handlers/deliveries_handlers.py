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
from app.models.event_projection import OrdersDeliveryProjection


def _upsert_orders_delivery_projection(db: Session, event: dict[str, Any]) -> None:
    data = get_event_data(event)
    delivery_id = str(data["delivery_id"])

    projection = get_or_create_projection(
        db,
        OrdersDeliveryProjection,
        lookup_field="delivery_id",
        lookup_value=delivery_id,
    )

    apply_values(
        projection,
        {
            "order_id": data.get("order_id"),
            "order_item_id": data.get("order_item_id"),
            "item_id": data.get("item_id"),
            "renter_id": data.get("renter_id"),
            "owner_id": data.get("owner_id"),
            "delivery_status": data.get("status"),
            "current_location": data.get("current_location"),
            "final_location": data.get("final_location"),
            "return_reason": data.get("return_reason"),
            **source_fields(event),
        },
    )


def handle_delivery_created(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "delivery_id", "order_id", "order_item_id", "item_id", "status")

    log_event_received(db=db, handler_name="handle_delivery_created", event=event)

    _upsert_orders_delivery_projection(db, event)

    return processed(
        "Delivery created event projected to orders delivery projection",
        target_contexts=["orders"],
    )


def handle_delivery_completed(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "delivery_id", "order_id", "order_item_id", "item_id", "status")

    log_event_received(db=db, handler_name="handle_delivery_completed", event=event)

    _upsert_orders_delivery_projection(db, event)

    return processed(
        "Delivery completed event projected to orders delivery projection",
        target_contexts=["orders"],
    )


def handle_delivery_return_requested(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "delivery_id", "order_id", "order_item_id", "item_id", "status")

    log_event_received(db=db, handler_name="handle_delivery_return_requested", event=event)

    _upsert_orders_delivery_projection(db, event)

    return processed(
        "Delivery return requested event projected to orders delivery projection",
        target_contexts=["orders"],
    )


def handle_delivery_cancelled(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "delivery_id", "order_id", "order_item_id", "item_id", "status")

    log_event_received(db=db, handler_name="handle_delivery_cancelled", event=event)

    _upsert_orders_delivery_projection(db, event)

    return processed(
        "Delivery cancelled event projected to orders delivery projection",
        target_contexts=["orders"],
    )