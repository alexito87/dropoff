from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.admin import require_admin
from app.events.delivery_events import (
    add_delivery_cancelled_event_to_outbox,
    add_delivery_completed_event_to_outbox,
    add_delivery_return_requested_event_to_outbox,
)
from app.models.audit_log_event import AuditLogEvent
from app.modules.admin.schemas.admin_deliveries import (
    AdminDeliveryActionPayload,
    AdminDeliveryCompletePayload,
    AdminDeliveryReturnRequestedPayload,
)
from app.modules.deliveries.models.delivery import Delivery
from app.modules.deliveries.schemas.delivery import DeliveryRead
from app.modules.orders.models.order import Order, OrderItem
from app.modules.users.models.user import User

router = APIRouter()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_delivery_or_404(db: Session, delivery_id: UUID) -> Delivery:
    delivery = db.query(Delivery).filter(Delivery.id == delivery_id).first()

    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")

    return delivery


def _get_order_or_404(db: Session, order_id: UUID) -> Order:
    order = db.query(Order).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return order


def _get_order_item(db: Session, order_item_id: UUID) -> OrderItem | None:
    return db.query(OrderItem).filter(OrderItem.id == order_item_id).first()


def _write_audit(
    db: Session,
    *,
    actor_user_id: UUID,
    action: str,
    delivery: Delivery,
    previous_delivery_status: str,
    new_delivery_status: str,
    order: Order | None,
    previous_order_status: str | None,
    new_order_status: str | None,
    order_item: OrderItem | None,
    previous_order_item_status: str | None,
    new_order_item_status: str | None,
    reason: str | None,
    extra: dict[str, Any] | None = None,
) -> None:
    meta = {
        "delivery_id": str(delivery.id),
        "order_id": str(delivery.order_id),
        "order_item_id": str(delivery.order_item_id),
        "previous_delivery_status": previous_delivery_status,
        "new_delivery_status": new_delivery_status,
        "previous_order_status": previous_order_status,
        "new_order_status": new_order_status,
        "previous_order_item_status": previous_order_item_status,
        "new_order_item_status": new_order_item_status,
        "reason": reason,
    }

    if extra:
        meta.update(extra)

    db.add(
        AuditLogEvent(
            actor_user_id=actor_user_id,
            action=action,
            entity_type="Delivery",
            entity_id=delivery.id,
            meta=meta,
        )
    )


def _delivery_result(
    *,
    action: str,
    delivery: Delivery,
    previous_delivery_status: str,
    order: Order | None,
    previous_order_status: str | None,
    order_item: OrderItem | None,
    previous_order_item_status: str | None,
    published_events: list[str],
    reason: str | None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = {
        "service": "admin-deliveries",
        "action": action,
        "delivery_id": str(delivery.id),
        "order_id": str(delivery.order_id),
        "order_item_id": str(delivery.order_item_id),
        "previous_delivery_status": previous_delivery_status,
        "new_delivery_status": delivery.status,
        "previous_order_status": previous_order_status,
        "new_order_status": order.status if order else None,
        "previous_order_item_status": previous_order_item_status,
        "new_order_item_status": order_item.status if order_item else None,
        "published_events": published_events,
        "reason": reason,
    }

    if extra:
        result.update(extra)

    return result


@router.get("/order/{order_id}", response_model=list[DeliveryRead])
def read_deliveries_by_order_as_admin(
    order_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    _get_order_or_404(db, order_id)

    deliveries = (
        db.query(Delivery)
        .filter(Delivery.order_id == order_id)
        .order_by(Delivery.updated_at.desc())
        .all()
    )

    return deliveries


@router.post("/{delivery_id}/cancel")
def cancel_delivery_as_admin(
    delivery_id: UUID,
    payload: AdminDeliveryActionPayload | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    delivery = _get_delivery_or_404(db, delivery_id)
    order = _get_order_or_404(db, delivery.order_id)
    order_item = _get_order_item(db, delivery.order_item_id)

    previous_delivery_status = delivery.status
    previous_order_status = order.status
    previous_order_item_status = order_item.status if order_item else None
    reason = payload.reason if payload else None
    now = _now()

    if delivery.status == "cancelled":
        return _delivery_result(
            action="delivery.cancel",
            delivery=delivery,
            previous_delivery_status=previous_delivery_status,
            order=order,
            previous_order_status=previous_order_status,
            order_item=order_item,
            previous_order_item_status=previous_order_item_status,
            published_events=[],
            reason=reason,
        )

    delivery.status = "cancelled"
    delivery.finished_at = delivery.finished_at or now
    delivery.updated_at = now

    if reason:
        delivery.return_reason = reason

    if order_item:
        order_item.status = "delivery_cancelled"
        order_item.updated_at = now
        db.add(order_item)

    order.status = "delivery_cancelled"
    order.updated_at = now

    db.add(delivery)
    db.add(order)

    add_delivery_cancelled_event_to_outbox(
        db,
        delivery=delivery,
        actor_user_id=current_user.id,
    )

    _write_audit(
        db,
        actor_user_id=current_user.id,
        action="delivery.cancel",
        delivery=delivery,
        previous_delivery_status=previous_delivery_status,
        new_delivery_status=delivery.status,
        order=order,
        previous_order_status=previous_order_status,
        new_order_status=order.status,
        order_item=order_item,
        previous_order_item_status=previous_order_item_status,
        new_order_item_status=order_item.status if order_item else None,
        reason=reason,
        extra={
            "published_events": ["delivery.cancelled"],
        },
    )

    db.commit()
    db.refresh(delivery)

    return _delivery_result(
        action="delivery.cancel",
        delivery=delivery,
        previous_delivery_status=previous_delivery_status,
        order=order,
        previous_order_status=previous_order_status,
        order_item=order_item,
        previous_order_item_status=previous_order_item_status,
        published_events=["delivery.cancelled"],
        reason=reason,
    )


@router.post("/{delivery_id}/force-complete")
def force_complete_delivery_as_admin(
    delivery_id: UUID,
    payload: AdminDeliveryCompletePayload | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    delivery = _get_delivery_or_404(db, delivery_id)
    order = _get_order_or_404(db, delivery.order_id)
    order_item = _get_order_item(db, delivery.order_item_id)

    previous_delivery_status = delivery.status
    previous_order_status = order.status
    previous_order_item_status = order_item.status if order_item else None
    reason = payload.reason if payload else None
    now = _now()

    delivery.status = "delivered"
    delivery.final_location = payload.final_location if payload else delivery.final_location
    delivery.finished_at = payload.finished_at if payload and payload.finished_at else delivery.finished_at or now
    delivery.updated_at = now

    if order_item:
        order_item.status = "active"
        order_item.updated_at = now
        db.add(order_item)

    if order.status in {"paid", "delivery_in_progress", "return_requested", "delivery_cancelled"}:
        order.status = "active"
        order.updated_at = now

    db.add(delivery)
    db.add(order)

    add_delivery_completed_event_to_outbox(
        db,
        delivery=delivery,
        actor_user_id=current_user.id,
    )

    _write_audit(
        db,
        actor_user_id=current_user.id,
        action="delivery.force_complete",
        delivery=delivery,
        previous_delivery_status=previous_delivery_status,
        new_delivery_status=delivery.status,
        order=order,
        previous_order_status=previous_order_status,
        new_order_status=order.status,
        order_item=order_item,
        previous_order_item_status=previous_order_item_status,
        new_order_item_status=order_item.status if order_item else None,
        reason=reason,
        extra={
            "final_location": delivery.final_location,
            "published_events": ["delivery.completed"],
        },
    )

    db.commit()
    db.refresh(delivery)

    return _delivery_result(
        action="delivery.force_complete",
        delivery=delivery,
        previous_delivery_status=previous_delivery_status,
        order=order,
        previous_order_status=previous_order_status,
        order_item=order_item,
        previous_order_item_status=previous_order_item_status,
        published_events=["delivery.completed"],
        reason=reason,
        extra={
            "final_location": delivery.final_location,
        },
    )


@router.post("/{delivery_id}/force-return-requested")
def force_return_requested_delivery_as_admin(
    delivery_id: UUID,
    payload: AdminDeliveryReturnRequestedPayload | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    delivery = _get_delivery_or_404(db, delivery_id)
    order = _get_order_or_404(db, delivery.order_id)
    order_item = _get_order_item(db, delivery.order_item_id)

    previous_delivery_status = delivery.status
    previous_order_status = order.status
    previous_order_item_status = order_item.status if order_item else None
    reason = payload.reason if payload else None
    now = _now()

    delivery.status = "return_requested"
    delivery.return_reason = reason
    delivery.updated_at = now

    if order_item:
        order_item.status = "return_requested"
        order_item.updated_at = now
        db.add(order_item)

    order.status = "return_requested"
    order.updated_at = now

    db.add(delivery)
    db.add(order)

    add_delivery_return_requested_event_to_outbox(
        db,
        delivery=delivery,
        actor_user_id=current_user.id,
    )

    _write_audit(
        db,
        actor_user_id=current_user.id,
        action="delivery.force_return_requested",
        delivery=delivery,
        previous_delivery_status=previous_delivery_status,
        new_delivery_status=delivery.status,
        order=order,
        previous_order_status=previous_order_status,
        new_order_status=order.status,
        order_item=order_item,
        previous_order_item_status=previous_order_item_status,
        new_order_item_status=order_item.status if order_item else None,
        reason=reason,
        extra={
            "published_events": ["delivery.return_requested"],
        },
    )

    db.commit()
    db.refresh(delivery)

    return _delivery_result(
        action="delivery.force_return_requested",
        delivery=delivery,
        previous_delivery_status=previous_delivery_status,
        order=order,
        previous_order_status=previous_order_status,
        order_item=order_item,
        previous_order_item_status=previous_order_item_status,
        published_events=["delivery.return_requested"],
        reason=reason,
    )