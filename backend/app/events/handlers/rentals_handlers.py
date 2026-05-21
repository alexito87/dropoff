from typing import Any

from sqlalchemy.orm import Session

from app.events.business_processes import apply_rental_event_to_order
from app.events.handlers.base import (
    EventHandlingResult,
    log_event_received,
    processed,
    require_data_fields,
    require_event_fields,
)
from app.events.rental_notification_processes import ensure_notifications_for_rental_event


def _handle_rental_event(
    db: Session,
    event: dict[str, Any],
    *,
    handler_name: str,
    message: str,
) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "rental_id", "item_id", "renter_id", "status", "start_date", "end_date")

    log_event_received(db=db, handler_name=handler_name, event=event)

    order_result = apply_rental_event_to_order(db, event)
    notification_result = ensure_notifications_for_rental_event(db, event)

    return processed(
        message,
        target_contexts=["orders", "notifications"],
        business_result={
            "order_result": order_result,
            "notification_result": notification_result,
        },
    )


def handle_rental_created(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    return _handle_rental_event(
        db,
        event,
        handler_name="handle_rental_created",
        message="Rental created event accepted and notification checked",
    )


def handle_rental_approved(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    return _handle_rental_event(
        db,
        event,
        handler_name="handle_rental_approved",
        message="Rental approved event accepted and notification checked",
    )


def handle_rental_rejected(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    return _handle_rental_event(
        db,
        event,
        handler_name="handle_rental_rejected",
        message="Rental rejected event accepted and notification checked",
    )


def handle_rental_started(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    return _handle_rental_event(
        db,
        event,
        handler_name="handle_rental_started",
        message="Rental started event applied to order and notification checked",
    )


def handle_rental_completed(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    return _handle_rental_event(
        db,
        event,
        handler_name="handle_rental_completed",
        message="Rental completed event applied to order and notification checked",
    )


def handle_rental_cancelled(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    return _handle_rental_event(
        db,
        event,
        handler_name="handle_rental_cancelled",
        message="Rental cancelled event applied to order and notification checked",
    )