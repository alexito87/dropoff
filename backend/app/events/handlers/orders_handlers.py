from typing import Any

from sqlalchemy.orm import Session

from app.events.business_processes import ensure_payment_for_order_created_event
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
from app.models.event_projection import DeliveriesOrderProjection, PaymentsOrderProjection


def _order_values(event: dict[str, Any]) -> dict[str, Any]:
    data = get_event_data(event)

    return {
        "user_id": data.get("user_id"),
        "order_status": data.get("status"),
        "payment_method": data.get("payment_method"),
        "delivery_method": data.get("delivery_method"),
        "total_amount_cents": data.get("total_amount_cents"),
        **source_fields(event),
    }


def _upsert_payments_order_projection(db: Session, event: dict[str, Any]) -> None:
    data = get_event_data(event)
    order_id = str(data["order_id"])

    projection = get_or_create_projection(
        db,
        PaymentsOrderProjection,
        lookup_field="order_id",
        lookup_value=order_id,
    )

    values = _order_values(event)
    values.pop("delivery_method", None)

    apply_values(projection, values)


def _upsert_deliveries_order_projection(db: Session, event: dict[str, Any]) -> None:
    data = get_event_data(event)
    order_id = str(data["order_id"])

    projection = get_or_create_projection(
        db,
        DeliveriesOrderProjection,
        lookup_field="order_id",
        lookup_value=order_id,
    )

    values = _order_values(event)
    values.pop("payment_method", None)

    apply_values(projection, values)


def _upsert_order_projections(db: Session, event: dict[str, Any]) -> None:
    _upsert_payments_order_projection(db, event)
    _upsert_deliveries_order_projection(db, event)


def handle_order_created(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "order_id", "user_id", "status", "total_amount_cents", "payment_method")

    log_event_received(db=db, handler_name="handle_order_created", event=event)

    _upsert_order_projections(db, event)

    payment_result = ensure_payment_for_order_created_event(db, event)

    return processed(
        "Order created event projected and payment creation checked",
        target_contexts=["payments", "deliveries"],
        business_result=payment_result,
    )


def handle_order_paid(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "order_id", "user_id", "status", "total_amount_cents")

    log_event_received(db=db, handler_name="handle_order_paid", event=event)

    _upsert_order_projections(db, event)

    return processed(
        "Order paid event projected to payments and deliveries order projections",
        target_contexts=["payments", "deliveries"],
    )


def handle_order_payment_failed(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "order_id", "user_id", "status")

    log_event_received(db=db, handler_name="handle_order_payment_failed", event=event)

    _upsert_order_projections(db, event)

    return processed(
        "Order payment failed event projected to payments and deliveries order projections",
        target_contexts=["payments", "deliveries"],
    )


def handle_order_payment_expired(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "order_id", "user_id", "status")

    log_event_received(db=db, handler_name="handle_order_payment_expired", event=event)

    _upsert_order_projections(db, event)

    return processed(
        "Order payment expired event projected to payments and deliveries order projections",
        target_contexts=["payments", "deliveries"],
    )


def handle_order_completed(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "order_id", "user_id", "status")

    log_event_received(db=db, handler_name="handle_order_completed", event=event)

    _upsert_order_projections(db, event)

    return processed(
        "Order completed event projected to payments and deliveries order projections",
        target_contexts=["payments", "deliveries"],
    )