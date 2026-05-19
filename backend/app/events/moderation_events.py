from sqlalchemy.orm import Session

from app.events.outbox import add_event_to_outbox
from app.events.schemas import EventEnvelope
from app.events.topics import ITEM_EVENTS_TOPIC, MODERATION_EVENTS_TOPIC


def _item_moderation_payload(item, *, actor_user_id, previous_status: str, decision: str) -> dict:
    return {
        "item_id": str(item.id),
        "owner_id": str(item.owner_id),
        "category_id": str(item.category_id),
        "title": item.title,
        "status": item.status,
        "previous_status": previous_status,
        "target_status": item.status,
        "decision": decision,
        "moderator_user_id": str(actor_user_id),
        "moderated_by": str(item.moderated_by) if item.moderated_by else None,
        "moderated_at": item.moderated_at.isoformat() if item.moderated_at else None,
        "moderation_comment": item.moderation_comment,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def add_item_approved_event_to_outbox(
    db: Session,
    *,
    item,
    actor_user_id,
    previous_status: str,
) -> None:
    moderation_event = EventEnvelope(
        event_type="moderation.item_approved",
        producer="moderation-endpoint",
        aggregate_type="Item",
        aggregate_id=str(item.id),
        data=_item_moderation_payload(
            item,
            actor_user_id=actor_user_id,
            previous_status=previous_status,
            decision="approved",
        ),
    )

    add_event_to_outbox(
        db,
        topic=MODERATION_EVENTS_TOPIC,
        event=moderation_event,
        key=str(item.id),
    )

    item_event = EventEnvelope(
        event_type="item.published",
        producer="moderation-endpoint",
        aggregate_type="Item",
        aggregate_id=str(item.id),
        data=_item_moderation_payload(
            item,
            actor_user_id=actor_user_id,
            previous_status=previous_status,
            decision="approved",
        ),
    )

    add_event_to_outbox(
        db,
        topic=ITEM_EVENTS_TOPIC,
        event=item_event,
        key=str(item.id),
    )


def add_item_rejected_event_to_outbox(
    db: Session,
    *,
    item,
    actor_user_id,
    previous_status: str,
) -> None:
    moderation_event = EventEnvelope(
        event_type="moderation.item_rejected",
        producer="moderation-endpoint",
        aggregate_type="Item",
        aggregate_id=str(item.id),
        data=_item_moderation_payload(
            item,
            actor_user_id=actor_user_id,
            previous_status=previous_status,
            decision="rejected",
        ),
    )

    add_event_to_outbox(
        db,
        topic=MODERATION_EVENTS_TOPIC,
        event=moderation_event,
        key=str(item.id),
    )

    item_event = EventEnvelope(
        event_type="item.rejected",
        producer="moderation-endpoint",
        aggregate_type="Item",
        aggregate_id=str(item.id),
        data=_item_moderation_payload(
            item,
            actor_user_id=actor_user_id,
            previous_status=previous_status,
            decision="rejected",
        ),
    )

    add_event_to_outbox(
        db,
        topic=ITEM_EVENTS_TOPIC,
        event=item_event,
        key=str(item.id),
    )


def add_item_needs_changes_event_to_outbox(
    db: Session,
    *,
    item,
    actor_user_id,
    previous_status: str,
) -> None:
    event = EventEnvelope(
        event_type="moderation.item_needs_changes",
        producer="moderation-endpoint",
        aggregate_type="Item",
        aggregate_id=str(item.id),
        data=_item_moderation_payload(
            item,
            actor_user_id=actor_user_id,
            previous_status=previous_status,
            decision="needs_changes",
        ),
    )

    add_event_to_outbox(
        db,
        topic=MODERATION_EVENTS_TOPIC,
        event=event,
        key=str(item.id),
    )