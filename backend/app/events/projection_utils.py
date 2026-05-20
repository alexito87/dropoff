from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session


def parse_event_datetime(value: Any) -> datetime | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        return value

    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)

    return None


def get_event_data(event: dict[str, Any]) -> dict[str, Any]:
    data = event.get("data")

    if isinstance(data, dict):
        return data

    return {}


def source_fields(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_event_id": str(event.get("event_id")),
        "source_event_type": str(event.get("event_type")),
        "source_payload": event,
        "occurred_at": parse_event_datetime(event.get("occurred_at")),
    }


def get_or_create_projection(
    db: Session,
    model,
    *,
    lookup_field: str,
    lookup_value: str,
):
    projection = (
        db.query(model)
        .filter(getattr(model, lookup_field) == lookup_value)
        .first()
    )

    if projection:
        return projection

    projection = model(**{lookup_field: lookup_value})
    db.add(projection)
    return projection


def apply_values(target, values: dict[str, Any]) -> None:
    for key, value in values.items():
        setattr(target, key, value)