from sqlalchemy.orm import Session

from app.events.outbox import add_event_to_outbox
from app.events.schemas import EventEnvelope
from app.events.topics import NOTIFICATION_EVENTS_TOPIC


def add_notification_created_event_to_outbox(
    db: Session,
    *,
    notification,
    producer: str = "notifications-helper",
) -> None:
    event = EventEnvelope(
        event_type="notification.created",
        producer=producer,
        aggregate_type="Notification",
        aggregate_id=str(notification.id),
        data={
            "notification_id": str(notification.id),
            "user_id": str(notification.user_id),
            "type": notification.type,
            "payload": notification.payload,
            "is_read": notification.is_read,
            "created_at": notification.created_at.isoformat()
            if notification.created_at
            else None,
        },
    )

    add_event_to_outbox(
        db,
        topic=NOTIFICATION_EVENTS_TOPIC,
        event=event,
        key=str(notification.user_id),
    )