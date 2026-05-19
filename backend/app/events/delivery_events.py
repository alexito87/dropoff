from sqlalchemy.orm import Session

from app.events.outbox import add_event_to_outbox
from app.events.schemas import EventEnvelope
from app.events.topics import DELIVERY_EVENTS_TOPIC


def _delivery_payload(delivery) -> dict:
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


def add_delivery_created_event_to_outbox(
    db: Session,
    *,
    delivery,
    actor_user_id,
) -> None:
    event = EventEnvelope(
        event_type="delivery.created",
        producer="deliveries-endpoint",
        aggregate_type="Delivery",
        aggregate_id=str(delivery.id),
        data={
            **_delivery_payload(delivery),
            "actor_user_id": str(actor_user_id),
        },
    )

    add_event_to_outbox(
        db,
        topic=DELIVERY_EVENTS_TOPIC,
        event=event,
        key=str(delivery.id),
    )


def add_delivery_completed_event_to_outbox(
    db: Session,
    *,
    delivery,
    actor_user_id,
) -> None:
    event = EventEnvelope(
        event_type="delivery.completed",
        producer="deliveries-endpoint",
        aggregate_type="Delivery",
        aggregate_id=str(delivery.id),
        data={
            **_delivery_payload(delivery),
            "actor_user_id": str(actor_user_id),
        },
    )

    add_event_to_outbox(
        db,
        topic=DELIVERY_EVENTS_TOPIC,
        event=event,
        key=str(delivery.id),
    )


def add_delivery_return_requested_event_to_outbox(
    db: Session,
    *,
    delivery,
    actor_user_id,
) -> None:
    event = EventEnvelope(
        event_type="delivery.return_requested",
        producer="deliveries-endpoint",
        aggregate_type="Delivery",
        aggregate_id=str(delivery.id),
        data={
            **_delivery_payload(delivery),
            "actor_user_id": str(actor_user_id),
        },
    )

    add_event_to_outbox(
        db,
        topic=DELIVERY_EVENTS_TOPIC,
        event=event,
        key=str(delivery.id),
    )


def add_delivery_cancelled_event_to_outbox(
    db: Session,
    *,
    delivery,
    actor_user_id,
) -> None:
    event = EventEnvelope(
        event_type="delivery.cancelled",
        producer="deliveries-endpoint",
        aggregate_type="Delivery",
        aggregate_id=str(delivery.id),
        data={
            **_delivery_payload(delivery),
            "actor_user_id": str(actor_user_id),
        },
    )

    add_event_to_outbox(
        db,
        topic=DELIVERY_EVENTS_TOPIC,
        event=event,
        key=str(delivery.id),
    )