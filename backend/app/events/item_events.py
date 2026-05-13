from sqlalchemy.orm import Session

from app.events.outbox import add_event_to_outbox
from app.events.schemas import EventEnvelope
from app.events.topics import CATALOG_EVENTS_TOPIC, MODERATION_EVENTS_TOPIC


def _item_payload(item) -> dict:
    return {
        "item_id": str(item.id),
        "owner_id": str(item.owner_id),
        "category_id": str(item.category_id),
        "title": item.title,
        "description": item.description,
        "status": item.status,
        "daily_price_cents": item.daily_price_cents,
        "deposit_cents": item.deposit_cents,
        "city": item.city,
        "pickup_address": item.pickup_address,
        "moderated_by": str(item.moderated_by) if item.moderated_by else None,
        "moderated_at": item.moderated_at.isoformat() if item.moderated_at else None,
        "moderation_comment": item.moderation_comment,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def add_item_created_event_to_outbox(
    db: Session,
    *,
    item,
    actor_user_id,
) -> None:
    """Создает событие после создания вещи в статусе draft."""
    event = EventEnvelope(
        event_type="item.created",
        producer="items-endpoint",
        aggregate_type="Item",
        aggregate_id=str(item.id),
        data={
            **_item_payload(item),
            "actor_user_id": str(actor_user_id),
        },
    )

    add_event_to_outbox(
        db,
        topic=CATALOG_EVENTS_TOPIC,
        event=event,
        key=str(item.id),
    )


def add_item_submitted_for_moderation_event_to_outbox(
    db: Session,
    *,
    item,
    actor_user_id,
    previous_status: str,
) -> None:
    """Создает событие после отправки вещи владельцем на модерацию."""
    event = EventEnvelope(
        event_type="item.submitted_for_moderation",
        producer="items-endpoint",
        aggregate_type="Item",
        aggregate_id=str(item.id),
        data={
            **_item_payload(item),
            "actor_user_id": str(actor_user_id),
            "previous_status": previous_status,
            "target_status": item.status,
            "images_count": len(item.images or []),
        },
    )

    add_event_to_outbox(
        db,
        topic=MODERATION_EVENTS_TOPIC,
        event=event,
        key=str(item.id),
    )
