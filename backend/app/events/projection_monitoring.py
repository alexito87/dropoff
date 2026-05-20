from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.event_projection import (
    AuditDomainEventProjection,
    CatalogItemProjection,
    DeliveriesOrderProjection,
    ModerationItemProjection,
    NotificationsUserProjection,
    OrdersCartProjection,
    OrdersDeliveryProjection,
    OrdersItemProjection,
    OrdersPaymentProjection,
    PaymentsOrderProjection,
)


PROJECTION_MODELS = {
    "catalog_item_projections": CatalogItemProjection,
    "moderation_item_projections": ModerationItemProjection,
    "orders_item_projections": OrdersItemProjection,
    "orders_cart_projections": OrdersCartProjection,
    "payments_order_projections": PaymentsOrderProjection,
    "deliveries_order_projections": DeliveriesOrderProjection,
    "orders_payment_projections": OrdersPaymentProjection,
    "orders_delivery_projections": OrdersDeliveryProjection,
    "notifications_user_projections": NotificationsUserProjection,
    "audit_domain_event_projections": AuditDomainEventProjection,
}


def get_projection_summary(db: Session) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "totals": {
            "all": 0,
        },
        "tables": {},
    }

    for table_name, model in PROJECTION_MODELS.items():
        count = db.query(func.count(model.id)).scalar() or 0
        count = int(count)

        summary["tables"][table_name] = {
            "rows": count,
        }
        summary["totals"]["all"] += count

    return summary


def _projection_to_dict(row) -> dict[str, Any]:
    result: dict[str, Any] = {}

    for column in row.__table__.columns:
        value = getattr(row, column.name)

        if hasattr(value, "isoformat"):
            value = value.isoformat()

        result[column.name] = str(value) if column.name == "id" and value is not None else value

    return result


def get_recent_projection_events(
    db: Session,
    *,
    table_name: str | None = None,
    source_event_type: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    if table_name:
        model = PROJECTION_MODELS.get(table_name)

        if model is None:
            return {
                "error": "unknown_projection_table",
                "available_tables": sorted(PROJECTION_MODELS.keys()),
                "events": [],
            }

        query = db.query(model)

        if source_event_type and hasattr(model, "source_event_type"):
            query = query.filter(model.source_event_type == source_event_type)

        if hasattr(model, "projected_at"):
            query = query.order_by(model.projected_at.desc())

        rows = query.limit(limit).all()

        return {
            "table": table_name,
            "events": [_projection_to_dict(row) for row in rows],
        }

    result: dict[str, Any] = {}

    for current_table_name, model in PROJECTION_MODELS.items():
        query = db.query(model)

        if source_event_type and hasattr(model, "source_event_type"):
            query = query.filter(model.source_event_type == source_event_type)

        if hasattr(model, "projected_at"):
            query = query.order_by(model.projected_at.desc())

        rows = query.limit(limit).all()

        result[current_table_name] = [_projection_to_dict(row) for row in rows]

    return {
        "tables": result,
    }


def get_available_projection_tables() -> list[str]:
    return sorted(PROJECTION_MODELS.keys())