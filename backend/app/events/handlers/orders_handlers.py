from typing import Any

from sqlalchemy.orm import Session

from app.events.handlers.base import (
    EventHandlingResult,
    log_event_received,
    processed,
    require_data_fields,
    require_event_fields,
)


def handle_order_created(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "order_id", "user_id", "status", "total_amount_cents", "payment_method")

    log_event_received(
        db=db,
        handler_name="handle_order_created",
        event=event,
    )

    return processed(
        "Order created event accepted for future payment/delivery/notification projection",
        target_contexts=["payments", "deliveries", "notifications", "audit"],
    )


def handle_order_paid(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "order_id", "user_id", "status", "total_amount_cents")

    log_event_received(
        db=db,
        handler_name="handle_order_paid",
        event=event,
    )

    return processed(
        "Order paid event accepted",
        target_contexts=["deliveries", "notifications", "audit"],
    )


def handle_order_payment_failed(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "order_id", "user_id", "status")

    log_event_received(
        db=db,
        handler_name="handle_order_payment_failed",
        event=event,
    )

    return processed(
        "Order payment failed event accepted",
        target_contexts=["payments", "notifications", "audit"],
    )


def handle_order_payment_expired(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "order_id", "user_id", "status")

    log_event_received(
        db=db,
        handler_name="handle_order_payment_expired",
        event=event,
    )

    return processed(
        "Order payment expired event accepted",
        target_contexts=["payments", "notifications", "audit"],
    )


def handle_order_completed(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "order_id", "user_id", "status")

    log_event_received(
        db=db,
        handler_name="handle_order_completed",
        event=event,
    )

    return processed(
        "Order completed event accepted",
        target_contexts=["notifications", "audit"],
    )