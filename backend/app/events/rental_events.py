from sqlalchemy.orm import Session

from app.events.outbox import add_event_to_outbox
from app.events.schemas import EventEnvelope
from app.events.topics import RENTAL_EVENTS_TOPIC


def _rental_payload(rental) -> dict:
    return {
        "rental_id": str(rental.id),
        "item_id": str(rental.item_id),
        "renter_id": str(rental.renter_id),
        "status": rental.status,
        "start_date": rental.start_date.isoformat() if rental.start_date else None,
        "end_date": rental.end_date.isoformat() if rental.end_date else None,
        "daily_price_cents": rental.daily_price_cents,
        "deposit_cents": rental.deposit_cents,
        "total_estimate_cents": rental.total_estimate_cents,
        "owner_comment": rental.owner_comment,
        "created_at": rental.created_at.isoformat() if rental.created_at else None,
        "updated_at": rental.updated_at.isoformat() if rental.updated_at else None,
    }


def add_rental_created_event_to_outbox(
    db: Session,
    *,
    rental,
    producer: str = "rentals-endpoint",
) -> None:
    event = EventEnvelope(
        event_type="rental.created",
        producer=producer,
        aggregate_type="Rental",
        aggregate_id=str(rental.id),
        data=_rental_payload(rental),
    )

    add_event_to_outbox(
        db,
        topic=RENTAL_EVENTS_TOPIC,
        event=event,
        key=str(rental.id),
    )


def add_rental_approved_event_to_outbox(
    db: Session,
    *,
    rental,
    producer: str = "rentals-endpoint",
) -> None:
    event = EventEnvelope(
        event_type="rental.approved",
        producer=producer,
        aggregate_type="Rental",
        aggregate_id=str(rental.id),
        data=_rental_payload(rental),
    )

    add_event_to_outbox(
        db,
        topic=RENTAL_EVENTS_TOPIC,
        event=event,
        key=str(rental.id),
    )


def add_rental_rejected_event_to_outbox(
    db: Session,
    *,
    rental,
    producer: str = "rentals-endpoint",
) -> None:
    event = EventEnvelope(
        event_type="rental.rejected",
        producer=producer,
        aggregate_type="Rental",
        aggregate_id=str(rental.id),
        data=_rental_payload(rental),
    )

    add_event_to_outbox(
        db,
        topic=RENTAL_EVENTS_TOPIC,
        event=event,
        key=str(rental.id),
    )


def add_rental_started_event_to_outbox(
    db: Session,
    *,
    rental,
    producer: str = "rentals-endpoint",
) -> None:
    event = EventEnvelope(
        event_type="rental.started",
        producer=producer,
        aggregate_type="Rental",
        aggregate_id=str(rental.id),
        data=_rental_payload(rental),
    )

    add_event_to_outbox(
        db,
        topic=RENTAL_EVENTS_TOPIC,
        event=event,
        key=str(rental.id),
    )


def add_rental_completed_event_to_outbox(
    db: Session,
    *,
    rental,
    producer: str = "rentals-endpoint",
) -> None:
    event = EventEnvelope(
        event_type="rental.completed",
        producer=producer,
        aggregate_type="Rental",
        aggregate_id=str(rental.id),
        data=_rental_payload(rental),
    )

    add_event_to_outbox(
        db,
        topic=RENTAL_EVENTS_TOPIC,
        event=event,
        key=str(rental.id),
    )


def add_rental_cancelled_event_to_outbox(
    db: Session,
    *,
    rental,
    producer: str = "rentals-endpoint",
) -> None:
    event = EventEnvelope(
        event_type="rental.cancelled",
        producer=producer,
        aggregate_type="Rental",
        aggregate_id=str(rental.id),
        data=_rental_payload(rental),
    )

    add_event_to_outbox(
        db,
        topic=RENTAL_EVENTS_TOPIC,
        event=event,
        key=str(rental.id),
    )