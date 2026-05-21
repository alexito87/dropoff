from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.admin import require_admin
from app.events.delivery_events import (
    add_delivery_completed_event_to_outbox,
    add_delivery_return_requested_event_to_outbox,
)
from app.events.event_dispatcher import dispatch_event
from app.events.order_events import (
    add_order_completed_event_to_outbox,
    add_order_paid_event_to_outbox,
    add_order_payment_expired_event_to_outbox,
    add_order_payment_failed_event_to_outbox,
)
from app.events.outbox import add_event_to_outbox
from app.events.payment_events import (
    add_payment_expired_event_to_outbox,
    add_payment_failed_event_to_outbox,
    add_payment_succeeded_event_to_outbox,
)
from app.events.rental_events import (
    add_rental_cancelled_event_to_outbox,
    add_rental_completed_event_to_outbox,
    add_rental_started_event_to_outbox,
)
from app.events.schemas import EventEnvelope
from app.events.topics import DELIVERY_EVENTS_TOPIC
from app.models.dead_letter_kafka_event import DeadLetterKafkaEvent
from app.modules.admin.schemas.admin_actions import (
    AdminDlqActionPayload,
    AdminStatusChangePayload,
)
from app.modules.deliveries.models.delivery import Delivery
from app.modules.orders.models.order import Order, OrderItem
from app.modules.payments.models.payment import Payment
from app.modules.rentals.models.rental import Rental
from app.modules.users.models.user import User

router = APIRouter()


ORDER_ALLOWED_STATUSES = {
    "awaiting_payment",
    "paid",
    "active",
    "completed",
    "payment_failed",
    "payment_expired",
    "cancelled",
}

PAYMENT_ALLOWED_STATUSES = {
    "pending",
    "checkout_creating",
    "checkout_created",
    "processing",
    "paid",
    "failed",
    "expired",
    "cancelled",
    "refunded",
}

DELIVERY_ALLOWED_STATUSES = {
    "in_progress",
    "delivered",
    "return_requested",
    "cancelled",
}

RENTAL_ALLOWED_STATUSES = {
    "pending",
    "approved",
    "active",
    "completed",
    "cancelled",
    "rejected",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_dlq_event_or_404(db: Session, dlq_event_id: UUID) -> DeadLetterKafkaEvent:
    event = db.query(DeadLetterKafkaEvent).filter(DeadLetterKafkaEvent.id == dlq_event_id).first()

    if not event:
        raise HTTPException(status_code=404, detail="DLQ event not found")

    return event


def _get_order_or_404(db: Session, order_id: UUID) -> Order:
    order = db.query(Order).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return order


def _get_payment_or_404(db: Session, payment_id: UUID) -> Payment:
    payment = db.query(Payment).filter(Payment.id == payment_id).first()

    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    return payment


def _get_delivery_or_404(db: Session, delivery_id: UUID) -> Delivery:
    delivery = db.query(Delivery).filter(Delivery.id == delivery_id).first()

    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")

    return delivery


def _get_rental_or_404(db: Session, rental_id: UUID) -> Rental:
    rental = db.query(Rental).filter(Rental.id == rental_id).first()

    if not rental:
        raise HTTPException(status_code=404, detail="Rental not found")

    return rental


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


def _delivery_payload(delivery: Delivery) -> dict[str, Any]:
    return {
        "delivery_id": str(delivery.id),
        "order_id": str(delivery.order_id),
        "order_item_id": str(delivery.order_item_id),
        "item_id": str(delivery.item_id),
        "renter_id": str(delivery.renter_id),
        "owner_id": str(delivery.owner_id),
        "status": delivery.status,
        "courier_name": delivery.courier_name,
        "current_location": delivery.current_location,
        "final_location": delivery.final_location,
        "return_reason": delivery.return_reason,
        "started_at": delivery.started_at.isoformat() if delivery.started_at else None,
        "finished_at": delivery.finished_at.isoformat() if delivery.finished_at else None,
        "created_at": delivery.created_at.isoformat() if delivery.created_at else None,
        "updated_at": delivery.updated_at.isoformat() if delivery.updated_at else None,
    }


def _add_delivery_cancelled_event_to_outbox(
    db: Session,
    *,
    delivery: Delivery,
    actor_user_id: UUID,
    reason: str | None,
) -> None:
    event = EventEnvelope(
        event_type="delivery.cancelled",
        producer="admin-actions",
        aggregate_type="Delivery",
        aggregate_id=str(delivery.id),
        data={
            **_delivery_payload(delivery),
            "actor_user_id": str(actor_user_id),
            "admin_reason": reason,
        },
    )

    add_event_to_outbox(
        db,
        topic=DELIVERY_EVENTS_TOPIC,
        event=event,
        key=str(delivery.id),
    )


def _dlq_to_dict(event: DeadLetterKafkaEvent) -> dict[str, Any]:
    return {
        "id": str(event.id),
        "consumer_name": event.consumer_name,
        "topic": event.topic,
        "partition": event.partition,
        "offset": event.offset,
        "event_key": event.event_key,
        "event_id": event.event_id,
        "event_type": event.event_type,
        "aggregate_type": event.aggregate_type,
        "aggregate_id": event.aggregate_id,
        "error_type": event.error_type,
        "error_message": event.error_message,
        "status": event.status,
        "created_at": event.created_at.isoformat() if event.created_at else None,
        "resolved_at": event.resolved_at.isoformat() if event.resolved_at else None,
    }


@router.post("/dlq/{dlq_event_id}/resolve")
def resolve_dlq_event_as_admin(
    dlq_event_id: UUID,
    payload: AdminDlqActionPayload | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    dlq_event = _get_dlq_event_or_404(db, dlq_event_id)
    dlq_event.status = "resolved"
    dlq_event.resolved_at = _now()

    db.add(dlq_event)
    db.commit()
    db.refresh(dlq_event)

    return {
        "service": "admin-actions",
        "action": "dlq.resolve",
        "reason": payload.reason if payload else None,
        "event": _dlq_to_dict(dlq_event),
    }


@router.post("/dlq/{dlq_event_id}/ignore")
def ignore_dlq_event_as_admin(
    dlq_event_id: UUID,
    payload: AdminDlqActionPayload | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    dlq_event = _get_dlq_event_or_404(db, dlq_event_id)
    dlq_event.status = "ignored"
    dlq_event.resolved_at = _now()

    db.add(dlq_event)
    db.commit()
    db.refresh(dlq_event)

    return {
        "service": "admin-actions",
        "action": "dlq.ignore",
        "reason": payload.reason if payload else None,
        "event": _dlq_to_dict(dlq_event),
    }


@router.post("/dlq/{dlq_event_id}/retry")
def retry_dlq_event_as_admin(
    dlq_event_id: UUID,
    payload: AdminDlqActionPayload | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    dlq_event = _get_dlq_event_or_404(db, dlq_event_id)

    if not isinstance(dlq_event.payload, dict):
        raise HTTPException(status_code=400, detail="DLQ payload is not a valid event object")

    result = dispatch_event(
        db,
        consumer_name=f"admin-dlq-retry:{current_user.id}",
        topic=dlq_event.topic,
        event=dlq_event.payload,
    )

    if result.status == "processed":
        dlq_event.status = "resolved"
        dlq_event.resolved_at = _now()
    elif result.status == "ignored":
        dlq_event.status = "ignored"
        dlq_event.resolved_at = _now()
    else:
        dlq_event.status = "retry_failed"

    db.add(dlq_event)
    db.commit()
    db.refresh(dlq_event)

    return {
        "service": "admin-actions",
        "action": "dlq.retry",
        "reason": payload.reason if payload else None,
        "handler_result": {
            "status": result.status,
            "message": result.message,
            "event_type": result.event_type,
            "event_id": result.event_id,
            "business_result": result.business_result,
        },
        "event": _dlq_to_dict(dlq_event),
    }


@router.post("/orders/{order_id}/status")
def force_order_status_as_admin(
    order_id: UUID,
    payload: AdminStatusChangePayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    target_status = payload.status.strip()

    if target_status not in ORDER_ALLOWED_STATUSES:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Unsupported order status",
                "allowed_statuses": sorted(ORDER_ALLOWED_STATUSES),
            },
        )

    order = _get_order_or_404(db, order_id)
    payment = _get_order_payment(db, order.id)
    previous_status = order.status
    now = _now()

    order.status = target_status
    order.updated_at = now

    changed_order_items = 0
    published_events: list[str] = []

    if target_status == "paid":
        order.paid_at = order.paid_at or now
        changed_order_items = _set_order_items_status(db, order_id=order.id, status="paid")

        if payment:
            payment.status = "paid"
            payment.paid_at = payment.paid_at or now
            payment.updated_at = now
            db.add(payment)

        add_order_paid_event_to_outbox(db, order=order, payment=payment)
        published_events.append("order.paid")

    elif target_status == "active":
        changed_order_items = _set_order_items_status(db, order_id=order.id, status="active")

    elif target_status == "completed":
        changed_order_items = _set_order_items_status(db, order_id=order.id, status="completed")
        add_order_completed_event_to_outbox(db, order=order)
        published_events.append("order.completed")

    elif target_status == "payment_failed":
        changed_order_items = _set_order_items_status(db, order_id=order.id, status="payment_failed")

        if payment:
            payment.status = "failed"
            payment.failed_at = payment.failed_at or now
            payment.updated_at = now
            db.add(payment)

        add_order_payment_failed_event_to_outbox(
            db,
            order=order,
            payment=payment,
            error_message=payload.reason,
        )
        published_events.append("order.payment_failed")

    elif target_status == "payment_expired":
        changed_order_items = _set_order_items_status(db, order_id=order.id, status="payment_expired")

        if payment:
            payment.status = "expired"
            payment.cancelled_at = payment.cancelled_at or now
            payment.updated_at = now
            db.add(payment)

        add_order_payment_expired_event_to_outbox(db, order=order, payment=payment)
        published_events.append("order.payment_expired")

    elif target_status == "cancelled":
        changed_order_items = _set_order_items_status(db, order_id=order.id, status="cancelled")

        if payment and payment.status not in {"paid", "refunded"}:
            payment.status = "cancelled"
            payment.cancelled_at = payment.cancelled_at or now
            payment.updated_at = now
            db.add(payment)

    db.add(order)
    db.commit()
    db.refresh(order)

    return {
        "service": "admin-actions",
        "action": "order.force_status",
        "order_id": str(order.id),
        "previous_status": previous_status,
        "new_status": order.status,
        "changed_order_items": changed_order_items,
        "published_events": published_events,
        "reason": payload.reason,
    }


@router.post("/payments/{payment_id}/status")
def force_payment_status_as_admin(
    payment_id: UUID,
    payload: AdminStatusChangePayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    target_status = payload.status.strip()

    if target_status not in PAYMENT_ALLOWED_STATUSES:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Unsupported payment status",
                "allowed_statuses": sorted(PAYMENT_ALLOWED_STATUSES),
            },
        )

    payment = _get_payment_or_404(db, payment_id)
    order = _get_order_or_404(db, payment.order_id)
    previous_status = payment.status
    now = _now()
    published_events: list[str] = []

    payment.status = target_status
    payment.updated_at = now

    if target_status == "paid":
        payment.paid_at = payment.paid_at or now
        order.status = "paid"
        order.paid_at = order.paid_at or now
        order.updated_at = now

        _set_order_items_status(db, order_id=order.id, status="paid")

        add_payment_succeeded_event_to_outbox(db, order=order, payment=payment)
        add_order_paid_event_to_outbox(db, order=order, payment=payment)
        published_events.extend(["payment.succeeded", "order.paid"])

    elif target_status == "failed":
        payment.failed_at = payment.failed_at or now
        order.status = "payment_failed"
        order.updated_at = now

        _set_order_items_status(db, order_id=order.id, status="payment_failed")

        add_payment_failed_event_to_outbox(
            db,
            order=order,
            payment=payment,
            error_message=payload.reason,
        )
        add_order_payment_failed_event_to_outbox(
            db,
            order=order,
            payment=payment,
            error_message=payload.reason,
        )
        published_events.extend(["payment.failed", "order.payment_failed"])

    elif target_status == "expired":
        payment.cancelled_at = payment.cancelled_at or now
        order.status = "payment_expired"
        order.updated_at = now

        _set_order_items_status(db, order_id=order.id, status="payment_expired")

        add_payment_expired_event_to_outbox(db, order=order, payment=payment)
        add_order_payment_expired_event_to_outbox(db, order=order, payment=payment)
        published_events.extend(["payment.expired", "order.payment_expired"])

    elif target_status == "cancelled":
        payment.cancelled_at = payment.cancelled_at or now

    db.add(payment)
    db.add(order)
    db.commit()
    db.refresh(payment)

    return {
        "service": "admin-actions",
        "action": "payment.force_status",
        "payment_id": str(payment.id),
        "order_id": str(order.id),
        "previous_status": previous_status,
        "new_status": payment.status,
        "published_events": published_events,
        "reason": payload.reason,
    }


@router.post("/deliveries/{delivery_id}/status")
def force_delivery_status_as_admin(
    delivery_id: UUID,
    payload: AdminStatusChangePayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    target_status = payload.status.strip()

    if target_status not in DELIVERY_ALLOWED_STATUSES:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Unsupported delivery status",
                "allowed_statuses": sorted(DELIVERY_ALLOWED_STATUSES),
            },
        )

    delivery = _get_delivery_or_404(db, delivery_id)
    order = _get_order_or_404(db, delivery.order_id)
    order_item = db.query(OrderItem).filter(OrderItem.id == delivery.order_item_id).first()
    previous_status = delivery.status
    now = _now()
    published_events: list[str] = []

    delivery.status = target_status
    delivery.updated_at = now

    if target_status == "in_progress":
        delivery.started_at = delivery.started_at or now

        if order_item:
            order_item.status = "in_delivery"
            order_item.updated_at = now
            db.add(order_item)

        if order.status == "paid":
            order.status = "delivery_in_progress"
            order.updated_at = now

    elif target_status == "delivered":
        delivery.finished_at = delivery.finished_at or now

        if order_item:
            order_item.status = "active"
            order_item.updated_at = now
            db.add(order_item)

        add_delivery_completed_event_to_outbox(
            db,
            delivery=delivery,
            actor_user_id=current_user.id,
        )
        published_events.append("delivery.completed")

    elif target_status == "return_requested":
        if order_item:
            order_item.status = "return_requested"
            order_item.updated_at = now
            db.add(order_item)

        order.status = "return_requested"
        order.updated_at = now

        add_delivery_return_requested_event_to_outbox(
            db,
            delivery=delivery,
            actor_user_id=current_user.id,
        )
        published_events.append("delivery.return_requested")

    elif target_status == "cancelled":
        delivery.finished_at = delivery.finished_at or now

        if order_item:
            order_item.status = "delivery_cancelled"
            order_item.updated_at = now
            db.add(order_item)

        order.status = "delivery_cancelled"
        order.updated_at = now

        _add_delivery_cancelled_event_to_outbox(
            db,
            delivery=delivery,
            actor_user_id=current_user.id,
            reason=payload.reason,
        )
        published_events.append("delivery.cancelled")

    db.add(delivery)
    db.add(order)
    db.commit()
    db.refresh(delivery)

    return {
        "service": "admin-actions",
        "action": "delivery.force_status",
        "delivery_id": str(delivery.id),
        "order_id": str(order.id),
        "previous_status": previous_status,
        "new_status": delivery.status,
        "published_events": published_events,
        "reason": payload.reason,
    }


@router.post("/rentals/{rental_id}/status")
def force_rental_status_as_admin(
    rental_id: UUID,
    payload: AdminStatusChangePayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    target_status = payload.status.strip()

    if target_status not in RENTAL_ALLOWED_STATUSES:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Unsupported rental status",
                "allowed_statuses": sorted(RENTAL_ALLOWED_STATUSES),
            },
        )

    rental = _get_rental_or_404(db, rental_id)
    previous_status = rental.status
    now = _now()
    published_events: list[str] = []

    rental.status = target_status
    rental.updated_at = now

    if target_status == "active":
        add_rental_started_event_to_outbox(db, rental=rental)
        published_events.append("rental.started")

    elif target_status == "completed":
        add_rental_completed_event_to_outbox(db, rental=rental)
        published_events.append("rental.completed")

    elif target_status == "cancelled":
        add_rental_cancelled_event_to_outbox(db, rental=rental)
        published_events.append("rental.cancelled")

    db.add(rental)
    db.commit()
    db.refresh(rental)

    return {
        "service": "admin-actions",
        "action": "rental.force_status",
        "rental_id": str(rental.id),
        "previous_status": previous_status,
        "new_status": rental.status,
        "published_events": published_events,
        "reason": payload.reason,
    }