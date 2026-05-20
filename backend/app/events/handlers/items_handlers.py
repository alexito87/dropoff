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
from app.models.event_projection import (
    CatalogItemProjection,
    ModerationItemProjection,
    OrdersItemProjection,
)


def _item_projection_values(event: dict[str, Any]) -> dict[str, Any]:
    data = get_event_data(event)

    return {
        "owner_id": data.get("owner_id"),
        "category_id": data.get("category_id"),
        "title": data.get("title"),
        "status": data.get("status") or data.get("target_status"),
        "daily_price_cents": data.get("daily_price_cents"),
        "deposit_cents": data.get("deposit_cents"),
        **source_fields(event),
    }


def _upsert_catalog_item_projection(db: Session, event: dict[str, Any]) -> None:
    data = get_event_data(event)
    item_id = str(data["item_id"])

    projection = get_or_create_projection(
        db,
        CatalogItemProjection,
        lookup_field="item_id",
        lookup_value=item_id,
    )

    values = _item_projection_values(event)
    values["city"] = data.get("city")

    apply_values(projection, values)


def _upsert_orders_item_projection(db: Session, event: dict[str, Any]) -> None:
    data = get_event_data(event)
    item_id = str(data["item_id"])

    projection = get_or_create_projection(
        db,
        OrdersItemProjection,
        lookup_field="item_id",
        lookup_value=item_id,
    )

    apply_values(projection, _item_projection_values(event))


def _upsert_moderation_item_projection(db: Session, event: dict[str, Any]) -> None:
    data = get_event_data(event)
    item_id = str(data["item_id"])

    projection = get_or_create_projection(
        db,
        ModerationItemProjection,
        lookup_field="item_id",
        lookup_value=item_id,
    )

    apply_values(
        projection,
        {
            "owner_id": data.get("owner_id"),
            "category_id": data.get("category_id"),
            "title": data.get("title"),
            "item_status": data.get("status") or data.get("target_status"),
            "moderation_status": data.get("decision") or data.get("status"),
            "moderation_comment": data.get("moderation_comment"),
            **source_fields(event),
        },
    )


def _upsert_common_item_projections(db: Session, event: dict[str, Any]) -> None:
    _upsert_catalog_item_projection(db, event)
    _upsert_orders_item_projection(db, event)


def handle_item_created(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "item_id", "owner_id", "category_id", "title", "status")

    log_event_received(db=db, handler_name="handle_item_created", event=event)

    _upsert_common_item_projections(db, event)

    return processed(
        "Item created event projected to catalog and orders item projections",
        target_contexts=["catalog", "orders"],
    )


def handle_item_updated(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "item_id", "owner_id", "category_id", "title", "status")

    log_event_received(db=db, handler_name="handle_item_updated", event=event)

    _upsert_common_item_projections(db, event)

    return processed(
        "Item updated event projected to catalog and orders item projections",
        target_contexts=["catalog", "orders"],
    )


def handle_item_deleted(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "item_id", "owner_id")

    log_event_received(db=db, handler_name="handle_item_deleted", event=event)

    _upsert_common_item_projections(db, event)

    return processed(
        "Item deleted event projected to catalog and orders item projections",
        target_contexts=["catalog", "orders"],
    )


def handle_item_submitted_for_moderation(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "item_id", "owner_id", "status")

    log_event_received(db=db, handler_name="handle_item_submitted_for_moderation", event=event)

    _upsert_common_item_projections(db, event)
    _upsert_moderation_item_projection(db, event)

    return processed(
        "Item submitted for moderation event projected",
        target_contexts=["catalog", "orders", "moderation"],
    )


def handle_item_published(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "item_id", "owner_id", "status")

    log_event_received(db=db, handler_name="handle_item_published", event=event)

    _upsert_common_item_projections(db, event)
    _upsert_moderation_item_projection(db, event)

    return processed(
        "Item published event projected",
        target_contexts=["catalog", "orders", "moderation"],
    )


def handle_item_rejected(db: Session, event: dict[str, Any]) -> EventHandlingResult:
    require_event_fields(event, "event_id", "event_type", "aggregate_type", "aggregate_id")
    require_data_fields(event, "item_id", "owner_id", "status")

    log_event_received(db=db, handler_name="handle_item_rejected", event=event)

    _upsert_common_item_projections(db, event)
    _upsert_moderation_item_projection(db, event)

    return processed(
        "Item rejected event projected",
        target_contexts=["catalog", "orders", "moderation"],
    )