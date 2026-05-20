import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.events.delivery_events import add_delivery_created_event_to_outbox
from app.events.order_events import (
    add_order_activated_event_to_outbox,
    add_order_paid_event_to_outbox,
    add_order_payment_expired_event_to_outbox,
    add_order_payment_failed_event_to_outbox,
)
from app.events.outbox import add_event_to_outbox
from app.events.projection_utils import get_event_data, parse_event_datetime
from app.events.schemas import EventEnvelope
from app.events.topics import PAYMENT_EVENTS_TOPIC
from app.modules.deliveries.models.delivery import Delivery
from app.modules.orders.models.order import Order, OrderItem
from app.modules.payments.models.payment import Payment


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_uuid(value: Any) -> uuid.UUID | None:
    if value in (None, ""):
        return None

    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def _event_time_or_now(event: dict[str, Any]) -> datetime:
    return parse_event_datetime(event.get("occurred_at")) or _now()


def _payment_payload(payment: Payment) -> dict[str, Any]:
    return {
        "payment_id": str(payment.id),
        "order_id": str(payment.order_id),
        "payer_user_id": str(payment.payer_user_id),
        "status": payment.status,
        "provider": payment.provider,
        "payment_method": payment.payment_method,
        "amount_total_cents": payment.amount_total_cents,
        "currency": payment.currency,
        "stripe_checkout_session_id": payment.stripe_checkout_session_id,
        "stripe_payment_intent_id": payment.stripe_payment_intent_id,
        "created_at": payment.created_at.isoformat() if payment.created_at else None,
        "updated_at": payment.updated_at.isoformat() if payment.updated_at else None,
        "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
        "failed_at": payment.failed_at.isoformat() if payment.failed_at else None,
        "cancelled_at": payment.cancelled_at.isoformat() if payment.cancelled_at else None,
    }


def add_payment_created_by_consumer_event_to_outbox(
    db: Session,
    *,
    payment: Payment,
) -> None:
    event = EventEnvelope(
        event_type="payment.created",
        producer="payments-consumer",
        aggregate_type="Payment",
        aggregate_id=str(payment.id),
        data=_payment_payload(payment),
    )

    add_event_to_outbox(
        db,
        topic=PAYMENT_EVENTS_TOPIC,
        event=event,
        key=str(payment.id),
    )


def ensure_payment_for_order_created_event(
    db: Session,
    event: dict[str, Any],
) -> dict[str, Any]:
    data = get_event_data(event)

    order_id = _parse_uuid(data.get("order_id"))
    user_id = _parse_uuid(data.get("user_id"))

    if order_id is None:
        return {
            "payment_created": False,
            "reason": "invalid_order_id",
        }

    order = db.query(Order).filter(Order.id == order_id).first()

    if order is None:
        return {
            "payment_created": False,
            "reason": "order_not_found",
            "order_id": str(order_id),
        }

    existing_payment = (
        db.query(Payment)
        .filter(Payment.order_id == order.id)
        .first()
    )

    if existing_payment:
        return {
            "payment_created": False,
            "reason": "payment_already_exists",
            "order_id": str(order.id),
            "payment_id": str(existing_payment.id),
        }

    payer_user_id = user_id or order.user_id

    payment = Payment(
        order_id=order.id,
        payer_user_id=payer_user_id,
        status="pending",
        provider="stripe",
        payment_method=data.get("payment_method") or order.payment_method or "stripe_checkout",
        amount_total_cents=data.get("total_amount_cents") or order.total_amount_cents,
        currency="usd",
        created_at=_now(),
        updated_at=_now(),
    )

    db.add(payment)
    db.flush()

    add_payment_created_by_consumer_event_to_outbox(
        db,
        payment=payment,
    )

    return {
        "payment_created": True,
        "reason": "payment_created_from_order_event",
        "order_id": str(order.id),
        "payment_id": str(payment.id),
    }


def _find_payment_for_event(
    db: Session,
    data: dict[str, Any],
) -> Payment | None:
    payment_id = _parse_uuid(data.get("payment_id"))

    if payment_id:
        payment = db.query(Payment).filter(Payment.id == payment_id).first()

        if payment:
            return payment

    order_id = _parse_uuid(data.get("order_id"))

    if order_id:
        return (
            db.query(Payment)
            .filter(Payment.order_id == order_id)
            .first()
        )

    return None


def _find_order_for_event(
    db: Session,
    data: dict[str, Any],
    payment: Payment | None,
) -> Order | None:
    order_id = _parse_uuid(data.get("order_id"))

    if order_id:
        order = db.query(Order).filter(Order.id == order_id).first()

        if order:
            return order

    if payment:
        return db.query(Order).filter(Order.id == payment.order_id).first()

    return None


def _update_order_items_status(
    db: Session,
    *,
    order_id: uuid.UUID,
    status: str,
) -> int:
    order_items = (
        db.query(OrderItem)
        .filter(OrderItem.order_id == order_id)
        .all()
    )

    changed = 0

    for order_item in order_items:
        if order_item.status != status:
            order_item.status = status
            order_item.updated_at = _now()
            db.add(order_item)
            changed += 1

    return changed


def _amount_matches_order(
    *,
    order: Order,
    data: dict[str, Any],
) -> bool:
    event_amount = data.get("amount_total_cents")

    if event_amount is None:
        return True

    try:
        return int(event_amount) == int(order.total_amount_cents)
    except (TypeError, ValueError):
        return False


def apply_payment_event_to_order(
    db: Session,
    event: dict[str, Any],
) -> dict[str, Any]:
    data = get_event_data(event)
    event_type = str(event.get("event_type") or "")
    occurred_at = _event_time_or_now(event)

    payment = _find_payment_for_event(db, data)
    order = _find_order_for_event(db, data, payment)

    if order is None:
        return {
            "order_updated": False,
            "reason": "order_not_found",
            "event_type": event_type,
            "order_id": data.get("order_id"),
            "payment_id": data.get("payment_id"),
        }

    if event_type == "payment.created":
        if payment:
            if payment.status != data.get("status", payment.status):
                payment.status = data.get("status", payment.status)
                payment.updated_at = _now()
                db.add(payment)

        return {
            "order_updated": False,
            "reason": "payment_created_does_not_change_order_status",
            "order_id": str(order.id),
            "payment_id": str(payment.id) if payment else data.get("payment_id"),
        }

    if event_type == "payment.checkout_session_created":
        if payment:
            payment.stripe_checkout_session_id = (
                data.get("stripe_checkout_session_id")
                or payment.stripe_checkout_session_id
            )
            payment.updated_at = _now()
            db.add(payment)

        return {
            "order_updated": False,
            "reason": "checkout_session_created_does_not_change_order_status",
            "order_id": str(order.id),
            "payment_id": str(payment.id) if payment else data.get("payment_id"),
        }

    if event_type == "payment.succeeded":
        if not _amount_matches_order(order=order, data=data):
            return {
                "order_updated": False,
                "reason": "payment_amount_does_not_match_order_total",
                "order_id": str(order.id),
                "payment_id": str(payment.id) if payment else data.get("payment_id"),
                "order_total_amount_cents": order.total_amount_cents,
                "payment_amount_total_cents": data.get("amount_total_cents"),
            }

        if payment:
            payment.status = "paid"
            payment.paid_at = payment.paid_at or occurred_at
            payment.stripe_checkout_session_id = (
                data.get("stripe_checkout_session_id")
                or payment.stripe_checkout_session_id
            )
            payment.stripe_payment_intent_id = (
                data.get("stripe_payment_intent_id")
                or payment.stripe_payment_intent_id
            )
            payment.updated_at = _now()
            db.add(payment)

        if order.status == "paid":
            return {
                "order_updated": False,
                "reason": "order_already_paid",
                "order_id": str(order.id),
                "payment_id": str(payment.id) if payment else data.get("payment_id"),
            }

        order.status = "paid"
        order.paid_at = order.paid_at or occurred_at
        order.updated_at = _now()
        db.add(order)

        changed_items = _update_order_items_status(
            db,
            order_id=order.id,
            status="paid",
        )

        add_order_paid_event_to_outbox(
            db,
            order=order,
            payment=payment,
        )

        return {
            "order_updated": True,
            "reason": "order_marked_paid",
            "order_id": str(order.id),
            "payment_id": str(payment.id) if payment else data.get("payment_id"),
            "changed_order_items": changed_items,
            "published_event": "order.paid",
        }

    if event_type == "payment.failed":
        if payment:
            payment.status = "failed"
            payment.failed_at = payment.failed_at or occurred_at
            payment.updated_at = _now()
            db.add(payment)

        if order.status == "payment_failed":
            return {
                "order_updated": False,
                "reason": "order_already_payment_failed",
                "order_id": str(order.id),
                "payment_id": str(payment.id) if payment else data.get("payment_id"),
            }

        order.status = "payment_failed"
        order.updated_at = _now()
        db.add(order)

        changed_items = _update_order_items_status(
            db,
            order_id=order.id,
            status="payment_failed",
        )

        add_order_payment_failed_event_to_outbox(
            db,
            order=order,
            payment=payment,
            error_message=data.get("error_message"),
        )

        return {
            "order_updated": True,
            "reason": "order_marked_payment_failed",
            "order_id": str(order.id),
            "payment_id": str(payment.id) if payment else data.get("payment_id"),
            "changed_order_items": changed_items,
            "published_event": "order.payment_failed",
        }

    if event_type == "payment.expired":
        if payment:
            payment.status = "expired"
            payment.cancelled_at = payment.cancelled_at or occurred_at
            payment.updated_at = _now()
            db.add(payment)

        if order.status == "payment_expired":
            return {
                "order_updated": False,
                "reason": "order_already_payment_expired",
                "order_id": str(order.id),
                "payment_id": str(payment.id) if payment else data.get("payment_id"),
            }

        order.status = "payment_expired"
        order.updated_at = _now()
        db.add(order)

        changed_items = _update_order_items_status(
            db,
            order_id=order.id,
            status="payment_expired",
        )

        add_order_payment_expired_event_to_outbox(
            db,
            order=order,
            payment=payment,
        )

        return {
            "order_updated": True,
            "reason": "order_marked_payment_expired",
            "order_id": str(order.id),
            "payment_id": str(payment.id) if payment else data.get("payment_id"),
            "changed_order_items": changed_items,
            "published_event": "order.payment_expired",
        }

    return {
        "order_updated": False,
        "reason": "payment_event_does_not_require_order_change",
        "event_type": event_type,
        "order_id": str(order.id),
        "payment_id": str(payment.id) if payment else data.get("payment_id"),
    }


def _find_order_for_delivery_event(
    db: Session,
    data: dict[str, Any],
) -> Order | None:
    order_id = _parse_uuid(data.get("order_id"))

    if order_id:
        return db.query(Order).filter(Order.id == order_id).first()

    return None


def _find_order_item_for_delivery_event(
    db: Session,
    data: dict[str, Any],
) -> OrderItem | None:
    order_item_id = _parse_uuid(data.get("order_item_id"))

    if order_item_id:
        return db.query(OrderItem).filter(OrderItem.id == order_item_id).first()

    return None


def _find_delivery_for_event(
    db: Session,
    data: dict[str, Any],
) -> Delivery | None:
    delivery_id = _parse_uuid(data.get("delivery_id"))

    if delivery_id:
        delivery = db.query(Delivery).filter(Delivery.id == delivery_id).first()

        if delivery:
            return delivery

    order_item_id = _parse_uuid(data.get("order_item_id"))

    if order_item_id:
        return (
            db.query(Delivery)
            .filter(Delivery.order_item_id == order_item_id)
            .first()
        )

    return None


def _all_order_items_have_status(
    db: Session,
    *,
    order_id: uuid.UUID,
    status: str,
) -> bool:
    order_items = (
        db.query(OrderItem)
        .filter(OrderItem.order_id == order_id)
        .all()
    )

    if not order_items:
        return False

    return all(order_item.status == status for order_item in order_items)


def ensure_deliveries_for_order_paid_event(
    db: Session,
    event: dict[str, Any],
) -> dict[str, Any]:
    data = get_event_data(event)
    order_id = _parse_uuid(data.get("order_id"))

    if order_id is None:
        return {
            "deliveries_created": 0,
            "reason": "invalid_order_id",
        }

    order = db.query(Order).filter(Order.id == order_id).first()

    if order is None:
        return {
            "deliveries_created": 0,
            "reason": "order_not_found",
            "order_id": str(order_id),
        }

    order_items = (
        db.query(OrderItem)
        .filter(OrderItem.order_id == order.id)
        .all()
    )

    if not order_items:
        return {
            "deliveries_created": 0,
            "reason": "order_has_no_items",
            "order_id": str(order.id),
        }

    created_deliveries: list[str] = []
    existing_deliveries: list[str] = []

    for order_item in order_items:
        existing_delivery = (
            db.query(Delivery)
            .filter(Delivery.order_item_id == order_item.id)
            .first()
        )

        if existing_delivery:
            existing_deliveries.append(str(existing_delivery.id))
            continue

        delivery = Delivery(
            order_id=order.id,
            order_item_id=order_item.id,
            renter_id=order.user_id,
            owner_id=order_item.owner_id,
            item_id=order_item.item_id,
            status="in_progress",
            started_at=_now(),
            created_at=_now(),
            updated_at=_now(),
        )

        db.add(delivery)
        db.flush()

        if order_item.status != "in_delivery":
            order_item.status = "in_delivery"
            order_item.updated_at = _now()
            db.add(order_item)

        add_delivery_created_event_to_outbox(
            db,
            delivery=delivery,
            actor_user_id=order.user_id,
        )

        created_deliveries.append(str(delivery.id))

    return {
        "deliveries_created": len(created_deliveries),
        "existing_deliveries": existing_deliveries,
        "created_delivery_ids": created_deliveries,
        "reason": "deliveries_created_from_order_paid_event",
        "order_id": str(order.id),
    }


def apply_delivery_event_to_order(
    db: Session,
    event: dict[str, Any],
) -> dict[str, Any]:
    data = get_event_data(event)
    event_type = str(event.get("event_type") or "")
    occurred_at = _event_time_or_now(event)

    delivery = _find_delivery_for_event(db, data)
    order = _find_order_for_delivery_event(db, data)
    order_item = _find_order_item_for_delivery_event(db, data)

    if order is None and delivery:
        order = db.query(Order).filter(Order.id == delivery.order_id).first()

    if order_item is None and delivery:
        order_item = (
            db.query(OrderItem)
            .filter(OrderItem.id == delivery.order_item_id)
            .first()
        )

    if order is None:
        return {
            "order_updated": False,
            "reason": "order_not_found",
            "event_type": event_type,
            "order_id": data.get("order_id"),
            "delivery_id": data.get("delivery_id"),
        }

    if delivery:
        delivery.current_location = data.get("current_location") or delivery.current_location
        delivery.final_location = data.get("final_location") or delivery.final_location
        delivery.return_reason = data.get("return_reason") or delivery.return_reason
        delivery.updated_at = _now()
        db.add(delivery)

    if event_type == "delivery.created":
        if delivery:
            delivery.status = data.get("status") or delivery.status or "in_progress"
            delivery.updated_at = _now()
            db.add(delivery)

        if order_item and order_item.status not in {"in_delivery", "active"}:
            order_item.status = "in_delivery"
            order_item.updated_at = _now()
            db.add(order_item)

        return {
            "order_updated": False,
            "reason": "delivery_created_marked_order_item_in_delivery",
            "order_id": str(order.id),
            "order_item_id": str(order_item.id) if order_item else data.get("order_item_id"),
            "delivery_id": str(delivery.id) if delivery else data.get("delivery_id"),
        }

    if event_type == "delivery.completed":
        if delivery:
            delivery.status = "delivered"
            delivery.finished_at = delivery.finished_at or occurred_at
            delivery.updated_at = _now()
            db.add(delivery)

        if order_item:
            order_item.status = "active"
            order_item.updated_at = _now()
            db.add(order_item)

        if _all_order_items_have_status(db, order_id=order.id, status="active"):
            if order.status != "active":
                order.status = "active"
                order.updated_at = _now()
                db.add(order)

                add_order_activated_event_to_outbox(
                    db,
                    order=order,
                )

                return {
                    "order_updated": True,
                    "reason": "all_deliveries_delivered_order_activated",
                    "order_id": str(order.id),
                    "order_item_id": str(order_item.id) if order_item else data.get("order_item_id"),
                    "delivery_id": str(delivery.id) if delivery else data.get("delivery_id"),
                    "published_event": "order.activated",
                }

            return {
                "order_updated": False,
                "reason": "order_already_active",
                "order_id": str(order.id),
                "order_item_id": str(order_item.id) if order_item else data.get("order_item_id"),
                "delivery_id": str(delivery.id) if delivery else data.get("delivery_id"),
            }

        return {
            "order_updated": False,
            "reason": "delivery_delivered_waiting_for_other_order_items",
            "order_id": str(order.id),
            "order_item_id": str(order_item.id) if order_item else data.get("order_item_id"),
            "delivery_id": str(delivery.id) if delivery else data.get("delivery_id"),
        }

    if event_type == "delivery.return_requested":
        if delivery:
            delivery.status = "return_requested"
            delivery.return_reason = data.get("return_reason") or delivery.return_reason
            delivery.updated_at = _now()
            db.add(delivery)

        if order_item:
            order_item.status = "return_requested"
            order_item.updated_at = _now()
            db.add(order_item)

        if order.status != "return_requested":
            order.status = "return_requested"
            order.updated_at = _now()
            db.add(order)

        return {
            "order_updated": True,
            "reason": "delivery_return_requested_applied_to_order",
            "order_id": str(order.id),
            "order_item_id": str(order_item.id) if order_item else data.get("order_item_id"),
            "delivery_id": str(delivery.id) if delivery else data.get("delivery_id"),
        }

    if event_type == "delivery.cancelled":
        if delivery:
            delivery.status = "cancelled"
            delivery.finished_at = delivery.finished_at or occurred_at
            delivery.updated_at = _now()
            db.add(delivery)

        if order_item:
            order_item.status = "delivery_cancelled"
            order_item.updated_at = _now()
            db.add(order_item)

        if order.status != "delivery_cancelled":
            order.status = "delivery_cancelled"
            order.updated_at = _now()
            db.add(order)

        return {
            "order_updated": True,
            "reason": "delivery_cancelled_applied_to_order",
            "order_id": str(order.id),
            "order_item_id": str(order_item.id) if order_item else data.get("order_item_id"),
            "delivery_id": str(delivery.id) if delivery else data.get("delivery_id"),
        }

    return {
        "order_updated": False,
        "reason": "delivery_event_does_not_require_order_change",
        "event_type": event_type,
        "order_id": str(order.id),
        "order_item_id": str(order_item.id) if order_item else data.get("order_item_id"),
        "delivery_id": str(delivery.id) if delivery else data.get("delivery_id"),
    }