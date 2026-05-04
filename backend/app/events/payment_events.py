from sqlalchemy.orm import Session

from app.events.outbox import add_event_to_outbox
from app.events.schemas import EventEnvelope
from app.events.topics import PAYMENT_EVENTS_TOPIC


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
            "order_id": str(order.id),
            "payment_id": str(payment.id),
            "user_id": str(order.user_id),
            "status": payment.status,
            "provider": payment.provider,
            "payment_method": payment.payment_method,
            "amount_total_cents": payment.amount_total_cents,
            "currency": payment.currency,
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
            "order_id": str(order.id),
            "payment_id": str(payment.id),
            "user_id": str(order.user_id),
            "status": payment.status,
            "provider": payment.provider,
            "payment_method": payment.payment_method,
            "amount_total_cents": payment.amount_total_cents,
            "currency": payment.currency,
            "stripe_checkout_session_id": stripe_checkout_session_id
            or payment.stripe_checkout_session_id,
            "stripe_payment_intent_id": stripe_payment_intent_id
            or payment.stripe_payment_intent_id,
            "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
        },
    )

    add_event_to_outbox(
        db,
        topic=PAYMENT_EVENTS_TOPIC,
        event=event,
        key=str(payment.id),
    )