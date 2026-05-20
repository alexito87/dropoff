import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EventHandlingResult:
    status: str
    message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class EventHandlerError(Exception):
    pass


def processed(message: str | None = None, **details: Any) -> EventHandlingResult:
    return EventHandlingResult(
        status="processed",
        message=message,
        details=details,
    )


def ignored(message: str | None = None, **details: Any) -> EventHandlingResult:
    return EventHandlingResult(
        status="ignored",
        message=message,
        details=details,
    )


def failed(message: str | None = None, **details: Any) -> EventHandlingResult:
    return EventHandlingResult(
        status="failed",
        message=message,
        details=details,
    )


def get_event_data(event: dict[str, Any]) -> dict[str, Any]:
    data = event.get("data")

    if data is None:
        return {}

    if not isinstance(data, dict):
        raise EventHandlerError("Event data must be a JSON object")

    return data


def require_event_fields(event: dict[str, Any], *field_names: str) -> None:
    missing_fields = [
        field_name
        for field_name in field_names
        if event.get(field_name) in (None, "")
    ]

    if missing_fields:
        raise EventHandlerError(
            f"Missing required event fields: {', '.join(missing_fields)}"
        )


def require_data_fields(event: dict[str, Any], *field_names: str) -> None:
    data = get_event_data(event)

    missing_fields = [
        field_name
        for field_name in field_names
        if data.get(field_name) in (None, "")
    ]

    if missing_fields:
        event_type = event.get("event_type", "unknown")
        raise EventHandlerError(
            f"Missing required data fields for {event_type}: {', '.join(missing_fields)}"
        )


def log_event_received(
    *,
    db: Session,
    handler_name: str,
    event: dict[str, Any],
) -> None:
    logger.info(
        "Business event handler called: handler=%s event_type=%s event_id=%s aggregate_type=%s aggregate_id=%s",
        handler_name,
        event.get("event_type"),
        event.get("event_id"),
        event.get("aggregate_type"),
        event.get("aggregate_id"),
    )