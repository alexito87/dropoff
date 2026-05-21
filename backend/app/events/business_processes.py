import uuid
from datetime import date, datetime, timezone
from typing import Any
import stripe
from app.modules.users.models.user import User

from sqlalchemy.orm import Session

from app.events.rental_events import (
    add_rental_created_event_to_outbox,
    add_rental_started_event_to_outbox,
)

from app.core.config import settings
from app.events.cart_events import add_cart_converted_to_order_event_to_outbox
from app.events.delivery_events import add_delivery_created_event_to_outbox
from app.events.item_events import (
    add_item_published_event_to_outbox as add_item_published_domain_event_to_outbox,
    add_item_rejected_event_to_outbox as add_item_rejected_domain_event_to_outbox,
)
from app.events.notification_events import add_notification_created_event_to_outbox
from app.events.order_events import (
    add_order_activated_event_to_outbox,
    add_order_completed_event_to_outbox,
    add_order_created_event_to_outbox,
    add_order_paid_event_to_outbox,
    add_order_payment_expired_event_to_outbox,
    add_order_payment_failed_event_to_outbox,
)
from app.events.outbox import add_event_to_outbox
from app.events.payment_events import (
    add_checkout_session_created_event_to_outbox,
    add_payment_created_event_to_outbox,
    add_payment_failed_event_to_outbox,
)
from app.events.projection_utils import get_event_data, parse_event_datetime
from app.events.schemas import EventEnvelope
from app.events.topics import PAYMENT_EVENTS_TOPIC
from app.modules.deliveries.models.delivery import Delivery
from app.modules.items.models.item import Item
from app.modules.notifications.models.notification import Notification
from app.modules.orders.models.cart import Cart, CartItem
from app.modules.orders.models.order import Order, OrderItem
from app.modules.payments.models.payment import (
    Payment,
    PaymentTransaction,
    StripeCheckoutSession,
)
from app.modules.rentals.models.rental import Rental


CHECKOUT_DELIVERY_METHODS = {
    "pickup": 0,
    "courier_standard": 1200,
}

CHECKOUT_SUPPORTED_PAYMENT_METHODS = {"stripe_checkout"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_uuid(value: Any) -> uuid.UUID | None:
    if value in (None, ""):
        return None

    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def _parse_date(value: Any) -> date | None:
    if value in (None, ""):
        return None

    if isinstance(value, date):
        return value

    try:
        return date.fromisoformat(str(value))
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


def _find_rental_for_event(
    db: Session,
    data: dict[str, Any],
) -> Rental | None:
    rental_id = _parse_uuid(data.get("rental_id"))

    if rental_id:
        rental = db.query(Rental).filter(Rental.id == rental_id).first()

        if rental:
            return rental

    item_id = _parse_uuid(data.get("item_id"))
    renter_id = _parse_uuid(data.get("renter_id"))

    if item_id and renter_id:
        return (
            db.query(Rental)
            .filter(
                Rental.item_id == item_id,
                Rental.renter_id == renter_id,
            )
            .order_by(Rental.updated_at.desc())
            .first()
        )

    return None


def _find_order_item_for_rental_event(
    db: Session,
    data: dict[str, Any],
) -> OrderItem | None:
    item_id = _parse_uuid(data.get("item_id"))
    renter_id = _parse_uuid(data.get("renter_id"))
    start_date = _parse_date(data.get("start_date"))
    end_date = _parse_date(data.get("end_date"))

    if item_id is None or renter_id is None:
        return None

    query = (
        db.query(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(
            OrderItem.item_id == item_id,
            Order.user_id == renter_id,
        )
    )

    if start_date is not None:
        query = query.filter(OrderItem.rent_start == start_date)

    if end_date is not None:
        query = query.filter(OrderItem.rent_end == end_date)

    return query.order_by(OrderItem.updated_at.desc()).first()


def apply_rental_event_to_order(
    db: Session,
    event: dict[str, Any],
) -> dict[str, Any]:
    data = get_event_data(event)
    event_type = str(event.get("event_type") or "")

    rental = _find_rental_for_event(db, data)
    order_item = _find_order_item_for_rental_event(db, data)

    if order_item is None:
        return {
            "order_updated": False,
            "reason": "order_item_not_found",
            "event_type": event_type,
            "rental_id": data.get("rental_id"),
            "item_id": data.get("item_id"),
            "renter_id": data.get("renter_id"),
        }

    order = db.query(Order).filter(Order.id == order_item.order_id).first()

    if order is None:
        return {
            "order_updated": False,
            "reason": "order_not_found",
            "event_type": event_type,
            "rental_id": data.get("rental_id"),
            "order_item_id": str(order_item.id),
        }

    if event_type == "rental.created":
        if rental and rental.status != data.get("status", rental.status):
            rental.status = data.get("status", rental.status)
            rental.updated_at = _now()
            db.add(rental)

        return {
            "order_updated": False,
            "reason": "rental_created_does_not_change_order_status",
            "order_id": str(order.id),
            "order_item_id": str(order_item.id),
            "rental_id": str(rental.id) if rental else data.get("rental_id"),
        }

    if event_type == "rental.started":
        if rental:
            rental.status = "active"
            rental.updated_at = _now()
            db.add(rental)

        if order_item.status != "active":
            order_item.status = "active"
            order_item.updated_at = _now()
            db.add(order_item)

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
            "reason": "rental_started_order_active",
            "order_id": str(order.id),
            "order_item_id": str(order_item.id),
            "rental_id": str(rental.id) if rental else data.get("rental_id"),
            "published_event": "order.activated",
        }

    if event_type == "rental.completed":
        if rental:
            rental.status = "completed"
            rental.updated_at = _now()
            db.add(rental)

        if order_item.status != "completed":
            order_item.status = "completed"
            order_item.updated_at = _now()
            db.add(order_item)

        if _all_order_items_have_status(db, order_id=order.id, status="completed"):
            if order.status != "completed":
                order.status = "completed"
                order.updated_at = _now()
                db.add(order)

                add_order_completed_event_to_outbox(
                    db,
                    order=order,
                )

                return {
                    "order_updated": True,
                    "reason": "all_rentals_completed_order_completed",
                    "order_id": str(order.id),
                    "order_item_id": str(order_item.id),
                    "rental_id": str(rental.id) if rental else data.get("rental_id"),
                    "published_event": "order.completed",
                }

            return {
                "order_updated": False,
                "reason": "order_already_completed",
                "order_id": str(order.id),
                "order_item_id": str(order_item.id),
                "rental_id": str(rental.id) if rental else data.get("rental_id"),
            }

        return {
            "order_updated": False,
            "reason": "rental_completed_waiting_for_other_order_items",
            "order_id": str(order.id),
            "order_item_id": str(order_item.id),
            "rental_id": str(rental.id) if rental else data.get("rental_id"),
        }

    if event_type == "rental.cancelled":
        if rental:
            rental.status = "cancelled"
            rental.updated_at = _now()
            db.add(rental)

        if order_item.status != "rental_cancelled":
            order_item.status = "rental_cancelled"
            order_item.updated_at = _now()
            db.add(order_item)

        if order.status != "rental_cancelled":
            order.status = "rental_cancelled"
            order.updated_at = _now()
            db.add(order)

        return {
            "order_updated": True,
            "reason": "rental_cancelled_applied_to_order",
            "order_id": str(order.id),
            "order_item_id": str(order_item.id),
            "rental_id": str(rental.id) if rental else data.get("rental_id"),
        }

    return {
        "order_updated": False,
        "reason": "rental_event_does_not_require_order_change",
        "event_type": event_type,
        "order_id": str(order.id),
        "order_item_id": str(order_item.id),
        "rental_id": str(rental.id) if rental else data.get("rental_id"),
    }


def create_order_from_cart_checkout_requested_event(
    db: Session,
    event: dict[str, Any],
) -> dict[str, Any]:
    data = get_event_data(event)

    cart_id = _parse_uuid(data.get("cart_id"))
    user_id = _parse_uuid(data.get("user_id"))
    delivery_method = data.get("delivery_method")
    payment_method = data.get("payment_method") or "stripe_checkout"

    if cart_id is None:
        return {
            "order_created": False,
            "reason": "invalid_cart_id",
        }

    if user_id is None:
        return {
            "order_created": False,
            "reason": "invalid_user_id",
            "cart_id": str(cart_id),
        }

    if delivery_method not in CHECKOUT_DELIVERY_METHODS:
        return {
            "order_created": False,
            "reason": "unsupported_delivery_method",
            "cart_id": str(cart_id),
            "delivery_method": delivery_method,
        }

    if payment_method not in CHECKOUT_SUPPORTED_PAYMENT_METHODS:
        return {
            "order_created": False,
            "reason": "unsupported_payment_method",
            "cart_id": str(cart_id),
            "payment_method": payment_method,
        }

    cart = (
        db.query(Cart)
        .filter(Cart.id == cart_id, Cart.user_id == user_id)
        .with_for_update()
        .first()
    )

    if cart is None:
        return {
            "order_created": False,
            "reason": "cart_not_found",
            "cart_id": str(cart_id),
            "user_id": str(user_id),
        }

    existing_order = (
        db.query(Order)
        .filter(Order.cart_id == cart.id)
        .order_by(Order.created_at.desc())
        .first()
    )

    if existing_order:
        return {
            "order_created": False,
            "reason": "order_already_exists_for_cart",
            "cart_id": str(cart.id),
            "order_id": str(existing_order.id),
            "order_status": existing_order.status,
        }

    if cart.status != "active":
        return {
            "order_created": False,
            "reason": "cart_is_not_active",
            "cart_id": str(cart.id),
            "cart_status": cart.status,
        }

    cart_items = (
        db.query(CartItem)
        .filter(CartItem.cart_id == cart.id)
        .order_by(CartItem.created_at.asc())
        .all()
    )

    if not cart_items:
        return {
            "order_created": False,
            "reason": "cart_is_empty",
            "cart_id": str(cart.id),
        }

    items_total = sum(item.rent_total_cents for item in cart_items)
    deposit_total = sum(item.total_deposit_cents for item in cart_items)
    delivery_fee = CHECKOUT_DELIVERY_METHODS[delivery_method]
    total_amount = items_total + deposit_total + delivery_fee
    now = _now()

    order = Order(
        user_id=user_id,
        cart_id=cart.id,
        status="awaiting_payment",
        delivery_method=delivery_method,
        payment_method=payment_method,
        items_total_cents=items_total,
        deposit_total_cents=deposit_total,
        delivery_fee_cents=delivery_fee,
        total_amount_cents=total_amount,
        created_at=now,
        updated_at=now,
    )
    db.add(order)
    db.flush()

    payment = Payment(
        order_id=order.id,
        payer_user_id=user_id,
        status="pending",
        provider="stripe",
        payment_method=payment_method,
        amount_total_cents=total_amount,
        currency=settings.stripe_currency,
        created_at=now,
        updated_at=now,
    )
    db.add(payment)
    db.flush()

    add_payment_created_event_to_outbox(
        db,
        payment=payment,
    )

    for cart_item in cart_items:
        item = db.query(Item).filter(Item.id == cart_item.item_id).first()

        if item is None:
            return {
                "order_created": False,
                "reason": "cart_item_item_not_found",
                "cart_id": str(cart.id),
                "cart_item_id": str(cart_item.id),
                "item_id": str(cart_item.item_id),
            }

        db.add(
            OrderItem(
                order_id=order.id,
                item_id=item.id,
                owner_id=item.owner_id,
                rent_start=cart_item.rent_start,
                rent_end=cart_item.rent_end,
                quantity=cart_item.quantity,
                status="awaiting_payment",
                daily_price_cents=cart_item.daily_price_cents,
                deposit_cents=cart_item.deposit_cents,
                rent_total_cents=cart_item.rent_total_cents,
                total_deposit_cents=cart_item.total_deposit_cents,
                line_total_cents=cart_item.rent_total_cents
                + cart_item.total_deposit_cents,
                created_at=now,
                updated_at=now,
            )
        )

    cart.status = "converted"
    cart.updated_at = now
    db.add(cart)

    add_order_created_event_to_outbox(
        db,
        order=order,
        payment=payment,
        cart=cart,
        cart_items=cart_items,
        user_id=user_id,
    )

    add_cart_converted_to_order_event_to_outbox(
        db,
        cart=cart,
        order=order,
        user_id=user_id,
    )

    return {
        "order_created": True,
        "reason": "order_created_from_cart_checkout_requested_event",
        "cart_id": str(cart.id),
        "order_id": str(order.id),
        "payment_id": str(payment.id),
        "order_status": order.status,
        "published_events": [
            "payment.created",
            "order.created",
            "cart.converted_to_order",
        ],
    }


def apply_moderation_event_to_item(
    db: Session,
    event: dict[str, Any],
) -> dict[str, Any]:
    data = get_event_data(event)
    event_type = str(event.get("event_type") or "")

    item_id = _parse_uuid(data.get("item_id"))
    moderator_user_id = _parse_uuid(data.get("moderator_user_id"))
    occurred_at = _event_time_or_now(event)

    if item_id is None:
        return {
            "item_updated": False,
            "reason": "invalid_item_id",
            "event_type": event_type,
        }

    item = db.query(Item).filter(Item.id == item_id).first()

    if item is None:
        return {
            "item_updated": False,
            "reason": "item_not_found",
            "event_type": event_type,
            "item_id": str(item_id),
        }

    previous_status = data.get("previous_status") or item.status
    moderation_comment = data.get("moderation_comment")

    if event_type == "moderation.item_approved":
        target_status = data.get("target_status") or "published"
        item.status = target_status
        item.moderated_by = moderator_user_id
        item.moderated_at = occurred_at
        item.moderation_comment = moderation_comment
        item.updated_at = _now()
        db.add(item)
        db.flush()

        notification = Notification(
            user_id=item.owner_id,
            type="item_approved",
            payload={
                "item_id": str(item.id),
                "title": item.title,
                "status": item.status,
                "moderator_user_id": str(moderator_user_id) if moderator_user_id else None,
            },
        )
        db.add(notification)
        db.flush()

        add_item_published_domain_event_to_outbox(
            db,
            item=item,
            moderator_user_id=moderator_user_id,
            previous_status=previous_status,
        )

        add_notification_created_event_to_outbox(
            db,
            notification=notification,
        )

        return {
            "item_updated": True,
            "reason": "moderation_approved_item_published",
            "item_id": str(item.id),
            "previous_status": previous_status,
            "target_status": item.status,
            "published_events": ["item.published", "notification.created"],
        }

    if event_type == "moderation.item_rejected":
        target_status = data.get("target_status") or "rejected"
        item.status = target_status
        item.moderated_by = moderator_user_id
        item.moderated_at = occurred_at
        item.moderation_comment = moderation_comment
        item.updated_at = _now()
        db.add(item)
        db.flush()

        notification = Notification(
            user_id=item.owner_id,
            type="item_rejected",
            payload={
                "item_id": str(item.id),
                "title": item.title,
                "status": item.status,
                "moderation_comment": item.moderation_comment,
                "moderator_user_id": str(moderator_user_id) if moderator_user_id else None,
            },
        )
        db.add(notification)
        db.flush()

        add_item_rejected_domain_event_to_outbox(
            db,
            item=item,
            moderator_user_id=moderator_user_id,
            previous_status=previous_status,
        )

        add_notification_created_event_to_outbox(
            db,
            notification=notification,
        )

        return {
            "item_updated": True,
            "reason": "moderation_rejected_item_rejected",
            "item_id": str(item.id),
            "previous_status": previous_status,
            "target_status": item.status,
            "published_events": ["item.rejected", "notification.created"],
        }

    if event_type == "moderation.item_needs_changes":
        target_status = data.get("target_status") or "rejected"
        item.status = target_status
        item.moderated_by = moderator_user_id
        item.moderated_at = occurred_at
        item.moderation_comment = moderation_comment
        item.updated_at = _now()
        db.add(item)
        db.flush()

        notification = Notification(
            user_id=item.owner_id,
            type="item_needs_changes",
            payload={
                "item_id": str(item.id),
                "title": item.title,
                "status": item.status,
                "moderation_comment": item.moderation_comment,
                "moderator_user_id": str(moderator_user_id) if moderator_user_id else None,
            },
        )
        db.add(notification)
        db.flush()

        add_item_rejected_domain_event_to_outbox(
            db,
            item=item,
            moderator_user_id=moderator_user_id,
            previous_status=previous_status,
        )

        add_notification_created_event_to_outbox(
            db,
            notification=notification,
        )

        return {
            "item_updated": True,
            "reason": "moderation_needs_changes_item_rejected",
            "item_id": str(item.id),
            "previous_status": previous_status,
            "target_status": item.status,
            "published_events": ["item.rejected", "notification.created"],
        }

    return {
        "item_updated": False,
        "reason": "moderation_event_does_not_require_item_change",
        "event_type": event_type,
        "item_id": str(item.id),
    }
def _stripe_datetime(timestamp_value: Any) -> datetime | None:
    if not timestamp_value:
        return None

    try:
        return datetime.fromtimestamp(int(timestamp_value), tz=timezone.utc)
    except (TypeError, ValueError):
        return None


def _stripe_value(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default

    if isinstance(obj, dict):
        return obj.get(key, default)

    return getattr(obj, key, default)


def _add_payment_transaction(
    db: Session,
    *,
    payment: Payment,
    tx_type: str,
    tx_status: str,
    provider_tx_id: str | None = None,
    error_message: str | None = None,
) -> PaymentTransaction:
    transaction = PaymentTransaction(
        payment_id=payment.id,
        order_id=payment.order_id,
        provider=payment.provider,
        type=tx_type,
        status=tx_status,
        amount_cents=payment.amount_total_cents,
        currency=payment.currency,
        provider_tx_id=provider_tx_id,
        error_message=error_message,
    )

    db.add(transaction)

    return transaction


def _build_checkout_line_items(
    db: Session,
    *,
    order: Order,
) -> list[dict[str, Any]]:
    order_items = (
        db.query(OrderItem)
        .filter(OrderItem.order_id == order.id)
        .order_by(OrderItem.created_at.asc())
        .all()
    )

    line_items: list[dict[str, Any]] = []

    for order_item in order_items:
        item = db.query(Item).filter(Item.id == order_item.item_id).first()
        item_title = item.title if item else f"Item {order_item.item_id}"

        line_items.append(
            {
                "price_data": {
                    "currency": settings.stripe_currency,
                    "unit_amount": order_item.line_total_cents,
                    "product_data": {
                        "name": item_title,
                        "description": (
                            f"Rental: {order_item.rent_start} — {order_item.rent_end}. "
                            f"Including deposit: {order_item.total_deposit_cents / 100:.2f} "
                            f"{settings.stripe_currency.upper()}"
                        ),
                    },
                },
                "quantity": order_item.quantity,
            }
        )

    if order.delivery_fee_cents > 0:
        line_items.append(
            {
                "price_data": {
                    "currency": settings.stripe_currency,
                    "unit_amount": order.delivery_fee_cents,
                    "product_data": {
                        "name": "Delivery",
                        "description": order.delivery_method,
                    },
                },
                "quantity": 1,
            }
        )

    return line_items


def ensure_checkout_session_for_payment_created_event(
    db: Session,
    event: dict[str, Any],
) -> dict[str, Any]:
    data = get_event_data(event)

    payment_id = _parse_uuid(data.get("payment_id"))
    order_id = _parse_uuid(data.get("order_id"))

    if payment_id is None:
        return {
            "checkout_session_created": False,
            "reason": "invalid_payment_id",
        }

    if order_id is None:
        return {
            "checkout_session_created": False,
            "reason": "invalid_order_id",
            "payment_id": str(payment_id),
        }

    payment = (
        db.query(Payment)
        .filter(Payment.id == payment_id)
        .with_for_update()
        .first()
    )

    if payment is None:
        return {
            "checkout_session_created": False,
            "reason": "payment_not_found",
            "payment_id": str(payment_id),
        }

    order = (
        db.query(Order)
        .filter(Order.id == order_id)
        .with_for_update()
        .first()
    )

    if order is None:
        return {
            "checkout_session_created": False,
            "reason": "order_not_found",
            "payment_id": str(payment.id),
            "order_id": str(order_id),
        }

    if payment.payment_method != "stripe_checkout":
        return {
            "checkout_session_created": False,
            "reason": "payment_method_does_not_need_checkout_session",
            "payment_id": str(payment.id),
            "payment_method": payment.payment_method,
        }

    if order.status != "awaiting_payment":
        return {
            "checkout_session_created": False,
            "reason": "order_is_not_awaiting_payment",
            "payment_id": str(payment.id),
            "order_id": str(order.id),
            "order_status": order.status,
        }

    existing_open_session = (
        db.query(StripeCheckoutSession)
        .filter(
            StripeCheckoutSession.payment_id == payment.id,
            StripeCheckoutSession.status == "open",
            StripeCheckoutSession.checkout_url.isnot(None),
        )
        .order_by(StripeCheckoutSession.created_at.desc())
        .first()
    )

    if existing_open_session:
        return {
            "checkout_session_created": False,
            "reason": "open_checkout_session_already_exists",
            "payment_id": str(payment.id),
            "order_id": str(order.id),
            "stripe_checkout_session_id": existing_open_session.provider_session_id,
            "checkout_url": existing_open_session.checkout_url,
        }

    if not settings.stripe_secret_key:
        return {
            "checkout_session_created": False,
            "reason": "stripe_secret_key_not_configured",
            "payment_id": str(payment.id),
            "order_id": str(order.id),
        }

    payer = db.query(User).filter(User.id == payment.payer_user_id).first()
    now = _now()

    local_session = StripeCheckoutSession(
        payment_id=payment.id,
        order_id=order.id,
        user_id=order.user_id,
        status="creating",
        payment_status="unpaid",
        amount_total_cents=payment.amount_total_cents,
        currency=payment.currency,
        created_at=now,
        updated_at=now,
    )

    payment.status = "checkout_creating"
    payment.updated_at = now

    _add_payment_transaction(
        db,
        payment=payment,
        tx_type="checkout_session_create_requested_by_consumer",
        tx_status="pending",
    )

    db.add(local_session)
    db.add(payment)
    db.flush()

    stripe.api_key = settings.stripe_secret_key

    success_url = (
        f"{settings.frontend_url}/orders/{order.id}/success"
        f"?session_id={{CHECKOUT_SESSION_ID}}"
    )
    cancel_url = f"{settings.frontend_url}/checkout?cancelled=1"

    try:
        stripe_session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            line_items=_build_checkout_line_items(db, order=order),
            customer_email=payer.email if payer else None,
            client_reference_id=str(order.id),
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "order_id": str(order.id),
                "payment_id": str(payment.id),
                "user_id": str(order.user_id),
                "created_by": "payment.created.consumer",
            },
            payment_intent_data={
                "metadata": {
                    "order_id": str(order.id),
                    "payment_id": str(payment.id),
                    "user_id": str(order.user_id),
                    "created_by": "payment.created.consumer",
                }
            },
            idempotency_key=f"dropoff-checkout-session-{order.id}-{payment.id}",
        )

    except stripe.StripeError as exc:
        now = _now()

        payment.status = "failed"
        payment.failed_at = payment.failed_at or now
        payment.updated_at = now

        order.status = "payment_failed"
        order.updated_at = now

        local_session.status = "failed"
        local_session.updated_at = now

        _add_payment_transaction(
            db,
            payment=payment,
            tx_type="checkout_session_create_failed_by_consumer",
            tx_status="failed",
            error_message=str(exc),
        )

        db.add(payment)
        db.add(order)
        db.add(local_session)

        add_order_payment_failed_event_to_outbox(
            db,
            order=order,
            payment=payment,
            error_message=str(exc),
        )

        add_payment_failed_event_to_outbox(
            db,
            order=order,
            payment=payment,
            error_message=str(exc),
        )

        return {
            "checkout_session_created": False,
            "reason": "stripe_error",
            "payment_id": str(payment.id),
            "order_id": str(order.id),
            "error": str(exc),
            "published_events": [
                "order.payment_failed",
                "payment.failed",
            ],
        }

    now = _now()

    local_session.provider_session_id = stripe_session.id
    local_session.status = _stripe_value(stripe_session, "status", "open") or "open"
    local_session.payment_status = (
        _stripe_value(stripe_session, "payment_status", "unpaid") or "unpaid"
    )
    local_session.checkout_url = _stripe_value(stripe_session, "url")
    local_session.expires_at = _stripe_datetime(_stripe_value(stripe_session, "expires_at"))
    local_session.updated_at = now

    payment.status = "checkout_created"
    payment.stripe_checkout_session_id = stripe_session.id
    payment.updated_at = now

    order.stripe_checkout_session_id = stripe_session.id
    order.updated_at = now

    _add_payment_transaction(
        db,
        payment=payment,
        tx_type="checkout_session_created_by_consumer",
        tx_status="success",
        provider_tx_id=stripe_session.id,
    )

    db.add(local_session)
    db.add(payment)
    db.add(order)

    add_checkout_session_created_event_to_outbox(
        db,
        order=order,
        payment=payment,
        checkout_session_id=stripe_session.id,
        checkout_url=_stripe_value(stripe_session, "url"),
    )

    return {
        "checkout_session_created": True,
        "reason": "checkout_session_created_from_payment_created_event",
        "payment_id": str(payment.id),
        "order_id": str(order.id),
        "stripe_checkout_session_id": stripe_session.id,
        "checkout_url": _stripe_value(stripe_session, "url"),
        "published_events": [
            "payment.checkout_session_created",
        ],
    }
def ensure_rental_for_delivery_completed_event(
    db: Session,
    event: dict[str, Any],
) -> dict[str, Any]:
    data = get_event_data(event)
    event_type = str(event.get("event_type") or "")

    if event_type != "delivery.completed":
        return {
            "rental_created": False,
            "reason": "event_is_not_delivery_completed",
            "event_type": event_type,
        }

    order_id = _parse_uuid(data.get("order_id"))
    order_item_id = _parse_uuid(data.get("order_item_id"))
    delivery_id = _parse_uuid(data.get("delivery_id"))

    if order_id is None:
        return {
            "rental_created": False,
            "reason": "invalid_order_id",
            "delivery_id": data.get("delivery_id"),
        }

    if order_item_id is None:
        return {
            "rental_created": False,
            "reason": "invalid_order_item_id",
            "order_id": str(order_id),
            "delivery_id": data.get("delivery_id"),
        }

    order = db.query(Order).filter(Order.id == order_id).first()

    if order is None:
        return {
            "rental_created": False,
            "reason": "order_not_found",
            "order_id": str(order_id),
            "delivery_id": str(delivery_id) if delivery_id else data.get("delivery_id"),
        }

    order_item = (
        db.query(OrderItem)
        .filter(OrderItem.id == order_item_id, OrderItem.order_id == order.id)
        .first()
    )

    if order_item is None:
        return {
            "rental_created": False,
            "reason": "order_item_not_found",
            "order_id": str(order.id),
            "order_item_id": str(order_item_id),
            "delivery_id": str(delivery_id) if delivery_id else data.get("delivery_id"),
        }

    existing_rental = (
        db.query(Rental)
        .filter(
            Rental.item_id == order_item.item_id,
            Rental.renter_id == order.user_id,
            Rental.start_date == order_item.rent_start,
            Rental.end_date == order_item.rent_end,
        )
        .order_by(Rental.created_at.desc())
        .first()
    )

    if existing_rental:
        return {
            "rental_created": False,
            "reason": "rental_already_exists",
            "order_id": str(order.id),
            "order_item_id": str(order_item.id),
            "rental_id": str(existing_rental.id),
            "rental_status": existing_rental.status,
        }

    rental = Rental(
        item_id=order_item.item_id,
        renter_id=order.user_id,
        status="active",
        start_date=order_item.rent_start,
        end_date=order_item.rent_end,
        daily_price_cents=order_item.daily_price_cents,
        deposit_cents=order_item.deposit_cents,
        total_estimate_cents=order_item.rent_total_cents + order_item.total_deposit_cents,
        owner_comment=(
            "Created automatically from delivery.completed"
            if delivery_id is None
            else f"Created automatically from delivery.completed: {delivery_id}"
        ),
        created_at=_now(),
        updated_at=_now(),
    )

    db.add(rental)
    db.flush()

    add_rental_created_event_to_outbox(
        db,
        rental=rental,
        producer="deliveries-consumer",
    )

    add_rental_started_event_to_outbox(
        db,
        rental=rental,
        producer="deliveries-consumer",
    )

    return {
        "rental_created": True,
        "reason": "rental_created_from_delivery_completed_event",
        "order_id": str(order.id),
        "order_item_id": str(order_item.id),
        "delivery_id": str(delivery_id) if delivery_id else data.get("delivery_id"),
        "rental_id": str(rental.id),
        "rental_status": rental.status,
        "published_events": [
            "rental.created",
            "rental.started",
        ],
    }