from sqlalchemy.orm import Session

from app.events.outbox import add_event_to_outbox
from app.events.schemas import EventEnvelope
from app.events.topics import ORDER_EVENTS_TOPIC


def _order_payload(order) -> dict:
    return {
        "order_id": str(order.id),
        "user_id": str(order.user_id),
        "cart_id": str(order.cart_id) if order.cart_id else None,
        "status": order.status,
        "delivery_method": order.delivery_method,
        "payment_method": order.payment_method,
        "items_total_cents": order.items_total_cents,
        "deposit_total_cents": order.deposit_total_cents,
        "delivery_fee_cents": order.delivery_fee_cents,
        "total_amount_cents": order.total_amount_cents,
        "stripe_checkout_session_id": order.stripe_checkout_session_id,
        "stripe_payment_intent_id": order.stripe_payment_intent_id,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "updated_at": order.updated_at.isoformat() if order.updated_at else None,
        "paid_at": order.paid_at.isoformat() if order.paid_at else None,
    }


def _payment_payload(payment) -> dict | None:
    if not payment:
        return None

    return {
        "payment_id": str(payment.id),
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


def _cart_item_payload(cart_item) -> dict:
    return {
        "cart_item_id": str(cart_item.id),
        "item_id": str(cart_item.item_id),
        "rent_start": cart_item.rent_start.isoformat(),
        "rent_end": cart_item.rent_end.isoformat(),
        "quantity": cart_item.quantity,
        "daily_price_cents": cart_item.daily_price_cents,
        "deposit_cents": cart_item.deposit_cents,
        "rent_total_cents": cart_item.rent_total_cents,
        "total_deposit_cents": cart_item.total_deposit_cents,
    }


def add_order_created_event_to_outbox(
    db: Session,
    *,
    order,
    payment,
    cart,
    cart_items,
    user_id,
) -> None:
    event = EventEnvelope(
        event_type="order.created",
        producer="orders-endpoint",
        aggregate_type="Order",
        aggregate_id=str(order.id),
        data={
            **_order_payload(order),
            "user_id": str(user_id),
            "cart_id": str(cart.id),
            "payment": _payment_payload(payment),
            "items": [_cart_item_payload(cart_item) for cart_item in cart_items],
        },
    )

    add_event_to_outbox(
        db,
        topic=ORDER_EVENTS_TOPIC,
        event=event,
        key=str(order.id),
    )


def add_order_paid_event_to_outbox(
    db: Session,
    *,
    order,
    payment,
) -> None:
    event = EventEnvelope(
        event_type="order.paid",
        producer="orders-endpoint",
        aggregate_type="Order",
        aggregate_id=str(order.id),
        data={
            **_order_payload(order),
            "payment": _payment_payload(payment),
        },
    )

    add_event_to_outbox(
        db,
        topic=ORDER_EVENTS_TOPIC,
        event=event,
        key=str(order.id),
    )


def add_order_payment_failed_event_to_outbox(
    db: Session,
    *,
    order,
    payment,
    error_message: str | None = None,
) -> None:
    event = EventEnvelope(
        event_type="order.payment_failed",
        producer="orders-endpoint",
        aggregate_type="Order",
        aggregate_id=str(order.id),
        data={
            **_order_payload(order),
            "payment": _payment_payload(payment),
            "error_message": error_message,
        },
    )

    add_event_to_outbox(
        db,
        topic=ORDER_EVENTS_TOPIC,
        event=event,
        key=str(order.id),
    )


def add_order_payment_expired_event_to_outbox(
    db: Session,
    *,
    order,
    payment,
) -> None:
    event = EventEnvelope(
        event_type="order.payment_expired",
        producer="orders-endpoint",
        aggregate_type="Order",
        aggregate_id=str(order.id),
        data={
            **_order_payload(order),
            "payment": _payment_payload(payment),
        },
    )

    add_event_to_outbox(
        db,
        topic=ORDER_EVENTS_TOPIC,
        event=event,
        key=str(order.id),
    )


def add_order_completed_event_to_outbox(
    db: Session,
    *,
    order,
) -> None:
    event = EventEnvelope(
        event_type="order.completed",
        producer="orders-endpoint",
        aggregate_type="Order",
        aggregate_id=str(order.id),
        data=_order_payload(order),
    )

    add_event_to_outbox(
        db,
        topic=ORDER_EVENTS_TOPIC,
        event=event,
        key=str(order.id),
    )