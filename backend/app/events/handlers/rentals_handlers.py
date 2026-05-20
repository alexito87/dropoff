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


def handle_rental_created(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "rental_id", "item_id", "renter_id", "status", "start_date", "end_date")

    log_event_received(db=db, handler_name="handle_rental_created", event=event)

    business_result = apply_rental_event_to_order(db, event)

    return processed(
        "Rental created event accepted",
        target_contexts=["orders"],
        business_result=business_result,
    )


def handle_rental_started(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "rental_id", "item_id", "renter_id", "status", "start_date", "end_date")

    log_event_received(db=db, handler_name="handle_rental_started", event=event)

    business_result = apply_rental_event_to_order(db, event)

    return processed(
        "Rental started event applied to order",
        target_contexts=["orders"],
        business_result=business_result,
    )


def handle_rental_completed(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "rental_id", "item_id", "renter_id", "status", "start_date", "end_date")

    log_event_received(db=db, handler_name="handle_rental_completed", event=event)

    business_result = apply_rental_event_to_order(db, event)

    return processed(
        "Rental completed event applied to order",
        target_contexts=["orders"],
        business_result=business_result,
    )


def handle_rental_cancelled(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "rental_id", "item_id", "renter_id", "status", "start_date", "end_date")

    log_event_received(db=db, handler_name="handle_rental_cancelled", event=event)

    business_result = apply_rental_event_to_order(db, event)

    return processed(
        "Rental cancelled event applied to order",
        target_contexts=["orders"],
        business_result=business_result,
    )