from typing import Any

from sqlalchemy.orm import Session

from app.events.handlers.base import (
    EventHandlingResult,
    log_event_received,
    processed,
    require_data_fields,
    require_event_fields,
)


def handle_payment_created(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "payment_id", "order_id", "payer_user_id", "status", "amount_total_cents")

    log_event_received(
        db=db,
        handler_name="handle_payment_created",
        event=event,
    )

    return processed(
        "Payment created event accepted",
        target_contexts=["orders", "audit"],
    )


def handle_payment_checkout_session_created(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "payment_id", "order_id", "status", "stripe_checkout_session_id")

    log_event_received(
        db=db,
        handler_name="handle_payment_checkout_session_created",
        event=event,
    )

    return processed(
        "Payment checkout session created event accepted",
        target_contexts=["orders", "notifications", "audit"],
    )


def handle_payment_succeeded(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "payment_id", "order_id", "status", "amount_total_cents")

    log_event_received(
        db=db,
        handler_name="handle_payment_succeeded",
        event=event,
    )

    return processed(
        "Payment succeeded event accepted for future orders projection",
        target_contexts=["orders", "notifications", "audit"],
    )


def handle_payment_failed(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "payment_id", "order_id", "status")

    log_event_received(
        db=db,
        handler_name="handle_payment_failed",
        event=event,
    )

    return processed(
        "Payment failed event accepted for future orders projection",
        target_contexts=["orders", "notifications", "audit"],
    )


def handle_payment_expired(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "payment_id", "order_id", "status")

    log_event_received(
        db=db,
        handler_name="handle_payment_expired",
        event=event,
    )

    return processed(
        "Payment expired event accepted for future orders projection",
        target_contexts=["orders", "notifications", "audit"],
    )