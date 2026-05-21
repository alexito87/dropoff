from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.admin import require_admin
from app.events.order_events import (
    add_order_activated_event_to_outbox,
    add_order_completed_event_to_outbox,
    add_order_paid_event_to_outbox,
    add_order_payment_expired_event_to_outbox,
    add_order_payment_failed_event_to_outbox,
)
from app.models.audit_log_event import AuditLogEvent
from app.modules.admin.schemas.admin_orders import AdminOrderActionPayload
from app.modules.orders.models.order import Order, OrderItem
from app.modules.payments.models.payment import Payment
from app.modules.users.models.user import User

router = APIRouter()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_order_or_404(db: Session, order_id: UUID) -> Order:
    order = db.query(Order).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return order


def _get_order_payment(db: Session, order_id: UUID) -> Payment | None:
    return (
        db.query(Payment)
        .filter(Payment.order_id == order_id)
        .order_by(Payment.created_at.desc())
        .first()
    )


def _set_order_items_status(
    db: Session,
    *,
    order_id: UUID,
    status: str,
) -> int:
    order_items = db.query(OrderItem).filter(OrderItem.order_id == order_id).all()
    changed = 0

    for order_item in order_items:
        if order_item.status != status:
            order_item.status = status
            order_item.updated_at = _now()
            db.add(order_item)
            changed += 1

    return changed


def _write_audit(
    db: Session,
    *,
    actor_user_id: UUID,
    action: str,
    order: Order,
    previous_status: str,
    new_status: str,
    reason: str | None,
    extra: dict[str, Any] | None = None,
) -> None:
    meta = {
        "previous_status": previous_status,
        "new_status": new_status,
        "reason": reason,
    }

    if extra:
        meta.update(extra)

    db.add(
        AuditLogEvent(
            actor_user_id=actor_user_id,
            action=action,
            entity_type="Order",
            entity_id=order.id,
            meta=meta,
        )
    )


def _order_result(
    *,
    action: str,
    order: Order,
    previous_status: str,
    changed_order_items: int,
    published_events: list[str],
    reason: str | None,
) -> dict[str, Any]:
    return {
        "service": "admin-orders",
        "action": action,
        "order_id": str(order.id),
        "previous_status": previous_status,
        "new_status": order.status,
        "changed_order_items": changed_order_items,
        "published_events": published_events,
        "reason": reason,
    }


@router.post("/{order_id}/cancel")
def cancel_order_as_admin(
    order_id: UUID,
    payload: AdminOrderActionPayload | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    order = _get_order_or_404(db, order_id)
    payment = _get_order_payment(db, order.id)
    previous_status = order.status
    reason = payload.reason if payload else None
    now = _now()

    if order.status == "cancelled":
        return _order_result(
            action="order.cancel",
            order=order,
            previous_status=previous_status,
            changed_order_items=0,
            published_events=[],
            reason=reason,
        )

    order.status = "cancelled"
    order.updated_at = now

    changed_order_items = _set_order_items_status(
        db,
        order_id=order.id,
        status="cancelled",
    )

    if payment and payment.status not in {"paid", "refunded"}:
        payment.status = "cancelled"
        payment.cancelled_at = payment.cancelled_at or now
        payment.updated_at = now
        db.add(payment)

    db.add(order)

    _write_audit(
        db,
        actor_user_id=current_user.id,
        action="order.cancel",
        order=order,
        previous_status=previous_status,
        new_status=order.status,
        reason=reason,
        extra={
            "payment_id": str(payment.id) if payment else None,
            "payment_status": payment.status if payment else None,
            "changed_order_items": changed_order_items,
        },
    )

    db.commit()
    db.refresh(order)

    return _order_result(
        action="order.cancel",
        order=order,
        previous_status=previous_status,
        changed_order_items=changed_order_items,
        published_events=[],
        reason=reason,
    )


@router.post("/{order_id}/mark-paid")
def mark_order_paid_as_admin(
    order_id: UUID,
    payload: AdminOrderActionPayload | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    order = _get_order_or_404(db, order_id)
    payment = _get_order_payment(db, order.id)
    previous_status = order.status
    reason = payload.reason if payload else None
    now = _now()

    order.status = "paid"
    order.paid_at = order.paid_at or now
    order.updated_at = now

    changed_order_items = _set_order_items_status(
        db,
        order_id=order.id,
        status="paid",
    )

    if payment:
        payment.status = "paid"
        payment.paid_at = payment.paid_at or now
        payment.updated_at = now
        db.add(payment)

    db.add(order)

    add_order_paid_event_to_outbox(
        db,
        order=order,
        payment=payment,
    )

    _write_audit(
        db,
        actor_user_id=current_user.id,
        action="order.mark_paid",
        order=order,
        previous_status=previous_status,
        new_status=order.status,
        reason=reason,
        extra={
            "payment_id": str(payment.id) if payment else None,
            "payment_status": payment.status if payment else None,
            "changed_order_items": changed_order_items,
            "published_events": ["order.paid"],
        },
    )

    db.commit()
    db.refresh(order)

    return _order_result(
        action="order.mark_paid",
        order=order,
        previous_status=previous_status,
        changed_order_items=changed_order_items,
        published_events=["order.paid"],
        reason=reason,
    )


@router.post("/{order_id}/mark-active")
def mark_order_active_as_admin(
    order_id: UUID,
    payload: AdminOrderActionPayload | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    order = _get_order_or_404(db, order_id)
    previous_status = order.status
    reason = payload.reason if payload else None

    order.status = "active"
    order.updated_at = _now()

    changed_order_items = _set_order_items_status(
        db,
        order_id=order.id,
        status="active",
    )

    db.add(order)

    add_order_activated_event_to_outbox(
        db,
        order=order,
    )

    _write_audit(
        db,
        actor_user_id=current_user.id,
        action="order.mark_active",
        order=order,
        previous_status=previous_status,
        new_status=order.status,
        reason=reason,
        extra={
            "changed_order_items": changed_order_items,
            "published_events": ["order.activated"],
        },
    )

    db.commit()
    db.refresh(order)

    return _order_result(
        action="order.mark_active",
        order=order,
        previous_status=previous_status,
        changed_order_items=changed_order_items,
        published_events=["order.activated"],
        reason=reason,
    )


@router.post("/{order_id}/mark-completed")
def mark_order_completed_as_admin(
    order_id: UUID,
    payload: AdminOrderActionPayload | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    order = _get_order_or_404(db, order_id)
    previous_status = order.status
    reason = payload.reason if payload else None

    order.status = "completed"
    order.updated_at = _now()

    changed_order_items = _set_order_items_status(
        db,
        order_id=order.id,
        status="completed",
    )

    db.add(order)

    add_order_completed_event_to_outbox(
        db,
        order=order,
    )

    _write_audit(
        db,
        actor_user_id=current_user.id,
        action="order.mark_completed",
        order=order,
        previous_status=previous_status,
        new_status=order.status,
        reason=reason,
        extra={
            "changed_order_items": changed_order_items,
            "published_events": ["order.completed"],
        },
    )

    db.commit()
    db.refresh(order)

    return _order_result(
        action="order.mark_completed",
        order=order,
        previous_status=previous_status,
        changed_order_items=changed_order_items,
        published_events=["order.completed"],
        reason=reason,
    )


@router.post("/{order_id}/mark-payment-failed")
def mark_order_payment_failed_as_admin(
    order_id: UUID,
    payload: AdminOrderActionPayload | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    order = _get_order_or_404(db, order_id)
    payment = _get_order_payment(db, order.id)
    previous_status = order.status
    reason = payload.reason if payload else None
    now = _now()

    order.status = "payment_failed"
    order.updated_at = now

    changed_order_items = _set_order_items_status(
        db,
        order_id=order.id,
        status="payment_failed",
    )

    if payment:
        payment.status = "failed"
        payment.failed_at = payment.failed_at or now
        payment.updated_at = now
        db.add(payment)

    db.add(order)

    add_order_payment_failed_event_to_outbox(
        db,
        order=order,
        payment=payment,
        error_message=reason,
    )

    _write_audit(
        db,
        actor_user_id=current_user.id,
        action="order.mark_payment_failed",
        order=order,
        previous_status=previous_status,
        new_status=order.status,
        reason=reason,
        extra={
            "payment_id": str(payment.id) if payment else None,
            "payment_status": payment.status if payment else None,
            "changed_order_items": changed_order_items,
            "published_events": ["order.payment_failed"],
        },
    )

    db.commit()
    db.refresh(order)

    return _order_result(
        action="order.mark_payment_failed",
        order=order,
        previous_status=previous_status,
        changed_order_items=changed_order_items,
        published_events=["order.payment_failed"],
        reason=reason,
    )


@router.post("/{order_id}/mark-payment-expired")
def mark_order_payment_expired_as_admin(
    order_id: UUID,
    payload: AdminOrderActionPayload | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    order = _get_order_or_404(db, order_id)
    payment = _get_order_payment(db, order.id)
    previous_status = order.status
    reason = payload.reason if payload else None
    now = _now()

    order.status = "payment_expired"
    order.updated_at = now

    changed_order_items = _set_order_items_status(
        db,
        order_id=order.id,
        status="payment_expired",
    )

    if payment:
        payment.status = "expired"
        payment.cancelled_at = payment.cancelled_at or now
        payment.updated_at = now
        db.add(payment)

    db.add(order)

    add_order_payment_expired_event_to_outbox(
        db,
        order=order,
        payment=payment,
    )

    _write_audit(
        db,
        actor_user_id=current_user.id,
        action="order.mark_payment_expired",
        order=order,
        previous_status=previous_status,
        new_status=order.status,
        reason=reason,
        extra={
            "payment_id": str(payment.id) if payment else None,
            "payment_status": payment.status if payment else None,
            "changed_order_items": changed_order_items,
            "published_events": ["order.payment_expired"],
        },
    )

    db.commit()
    db.refresh(order)

    return _order_result(
        action="order.mark_payment_expired",
        order=order,
        previous_status=previous_status,
        changed_order_items=changed_order_items,
        published_events=["order.payment_expired"],
        reason=reason,
    )