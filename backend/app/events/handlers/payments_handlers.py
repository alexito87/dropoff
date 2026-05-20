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
from app.models.event_projection import OrdersPaymentProjection


def _upsert_orders_payment_projection(db: Session, event: dict[str, Any]) -> None:
    data = get_event_data(event)
    payment_id = str(data["payment_id"])

    projection = get_or_create_projection(
        db,
        OrdersPaymentProjection,
        lookup_field="payment_id",
        lookup_value=payment_id,
    )

    apply_values(
        projection,
        {
            "order_id": data.get("order_id"),
            "payer_user_id": data.get("payer_user_id") or data.get("user_id"),
            "payment_status": data.get("status"),
            "provider": data.get("provider"),
            "payment_method": data.get("payment_method"),
            "amount_total_cents": data.get("amount_total_cents"),
            "currency": data.get("currency"),
            "stripe_checkout_session_id": data.get("stripe_checkout_session_id"),
            "stripe_payment_intent_id": data.get("stripe_payment_intent_id"),
            **source_fields(event),
        },
    )


def handle_payment_created(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "payment_id", "order_id", "payer_user_id", "status", "amount_total_cents")

    log_event_received(db=db, handler_name="handle_payment_created", event=event)

    _upsert_orders_payment_projection(db, event)

    return processed(
        "Payment created event projected to orders payment projection",
        target_contexts=["orders"],
    )


def handle_payment_checkout_session_created(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "payment_id", "order_id", "status", "stripe_checkout_session_id")

    log_event_received(db=db, handler_name="handle_payment_checkout_session_created", event=event)

    _upsert_orders_payment_projection(db, event)

    return processed(
        "Payment checkout session created event projected to orders payment projection",
        target_contexts=["orders"],
    )


def handle_payment_succeeded(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "payment_id", "order_id", "status", "amount_total_cents")

    log_event_received(db=db, handler_name="handle_payment_succeeded", event=event)

    _upsert_orders_payment_projection(db, event)

    return processed(
        "Payment succeeded event projected to orders payment projection",
        target_contexts=["orders"],
    )


def handle_payment_failed(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "payment_id", "order_id", "status")

    log_event_received(db=db, handler_name="handle_payment_failed", event=event)

    _upsert_orders_payment_projection(db, event)

    return processed(
        "Payment failed event projected to orders payment projection",
        target_contexts=["orders"],
    )


def handle_payment_expired(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "payment_id", "order_id", "status")

    log_event_received(db=db, handler_name="handle_payment_expired", event=event)

    _upsert_orders_payment_projection(db, event)

    return processed(
        "Payment expired event projected to orders payment projection",
        target_contexts=["orders"],
    )