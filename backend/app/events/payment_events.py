from sqlalchemy.orm import Session

from app.events.outbox import add_event_to_outbox
from app.events.schemas import EventEnvelope
from app.events.topics import PAYMENT_EVENTS_TOPIC


def _payment_payload(payment) -> dict:
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


def add_payment_created_event_to_outbox(
    db: Session,
    *,
    payment,
) -> None:
    event = EventEnvelope(
        event_type="payment.created",
        producer="orders-endpoint",
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


def add_checkout_session_created_event_to_outbox(
    db: Session,
    *,
    order,
    payment,
    checkout_session_id: str,
    checkout_url: str | None,
) -> None:
    event = EventEnvelope(
        event_type="payment.checkout_session_created",
        producer="orders-endpoint",
        aggregate_type="Payment",
        aggregate_id=str(payment.id),
        data={
            **_payment_payload(payment),
            "order_id": str(order.id),
            "user_id": str(order.user_id),
            "stripe_checkout_session_id": checkout_session_id,
            "checkout_url": checkout_url,
        },
    )

    add_event_to_outbox(
        db,
        topic=PAYMENT_EVENTS_TOPIC,
        event=event,
        key=str(payment.id),
    )


def add_payment_succeeded_event_to_outbox(
    db: Session,
    *,
    order,
    payment,
    stripe_checkout_session_id: str | None = None,
    stripe_payment_intent_id: str | None = None,
) -> None:
    event = EventEnvelope(
        event_type="payment.succeeded",
        producer="orders-endpoint",
        aggregate_type="Payment",
        aggregate_id=str(payment.id),
        data={
            **_payment_payload(payment),
            "order_id": str(order.id),
            "user_id": str(order.user_id),
            "stripe_checkout_session_id": stripe_checkout_session_id
            or payment.stripe_checkout_session_id,
            "stripe_payment_intent_id": stripe_payment_intent_id
            or payment.stripe_payment_intent_id,
        },
    )

    add_event_to_outbox(
        db,
        topic=PAYMENT_EVENTS_TOPIC,
        event=event,
        key=str(payment.id),
    )


def add_payment_failed_event_to_outbox(
    db: Session,
    *,
    order,
    payment,
    error_message: str | None = None,
) -> None:
    event = EventEnvelope(
        event_type="payment.failed",
        producer="orders-endpoint",
        aggregate_type="Payment",
        aggregate_id=str(payment.id),
        data={
            **_payment_payload(payment),
            "order_id": str(order.id),
            "user_id": str(order.user_id),
            "error_message": error_message,
        },
    )

    add_event_to_outbox(
        db,
        topic=PAYMENT_EVENTS_TOPIC,
        event=event,
        key=str(payment.id),
    )


def add_payment_expired_event_to_outbox(
    db: Session,
    *,
    order,
    payment,
) -> None:
    event = EventEnvelope(
        event_type="payment.expired",
        producer="orders-endpoint",
        aggregate_type="Payment",
        aggregate_id=str(payment.id),
        data={
            **_payment_payload(payment),
            "order_id": str(order.id),
            "user_id": str(order.user_id),
        },
    )

    add_event_to_outbox(
        db,
        topic=PAYMENT_EVENTS_TOPIC,
        event=event,
        key=str(payment.id),
    )