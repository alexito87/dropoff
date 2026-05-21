import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.events.notification_events import add_notification_created_event_to_outbox
from app.events.projection_utils import get_event_data
from app.modules.items.models.item import Item
from app.modules.notifications.models.notification import Notification


def _parse_uuid(value: Any) -> uuid.UUID | None:
    if value in (None, ""):
        return None

    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def _notification_already_exists(
    db: Session,
    *,
    user_id: uuid.UUID,
    notification_type: str,
    rental_id: str,
    status: str | None,
) -> bool:
    recent_notifications = (
        db.query(Notification)
        .filter(
            Notification.user_id == user_id,
            Notification.type == notification_type,
        )
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )

    for notification in recent_notifications:
        payload = notification.payload or {}

        if payload.get("rental_id") != rental_id:
            continue

        if status is not None and payload.get("status") != status:
            continue

        return True

    return False


def _create_notification_once(
    db: Session,
    *,
    user_id: uuid.UUID,
    notification_type: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    rental_id = str(payload.get("rental_id") or "")
    status = payload.get("status")

    if _notification_already_exists(
        db,
        user_id=user_id,
        notification_type=notification_type,
        rental_id=rental_id,
        status=status,
    ):
        return {
            "created": False,
            "reason": "notification_already_exists",
            "user_id": str(user_id),
            "type": notification_type,
            "rental_id": rental_id,
        }

    notification = Notification(
        user_id=user_id,
        type=notification_type,
        payload=payload,
    )

    db.add(notification)
    db.flush()

    add_notification_created_event_to_outbox(
        db,
        notification=notification,
        producer="rentals-consumer",
    )

    return {
        "created": True,
        "reason": "notification_created",
        "notification_id": str(notification.id),
        "user_id": str(user_id),
        "type": notification_type,
        "rental_id": rental_id,
        "published_event": "notification.created",
    }


def ensure_notifications_for_rental_event(
    db: Session,
    event: dict[str, Any],
) -> dict[str, Any]:
    data = get_event_data(event)
    event_type = str(event.get("event_type") or "")

    rental_id = data.get("rental_id")
    item_id = _parse_uuid(data.get("item_id"))
    renter_id = _parse_uuid(data.get("renter_id"))

    if not rental_id:
        return {
            "notifications_created": 0,
            "reason": "invalid_rental_id",
            "event_type": event_type,
        }

    if item_id is None:
        return {
            "notifications_created": 0,
            "reason": "invalid_item_id",
            "event_type": event_type,
            "rental_id": rental_id,
        }

    if renter_id is None:
        return {
            "notifications_created": 0,
            "reason": "invalid_renter_id",
            "event_type": event_type,
            "rental_id": rental_id,
        }

    item = db.query(Item).filter(Item.id == item_id).first()

    if item is None:
        return {
            "notifications_created": 0,
            "reason": "item_not_found",
            "event_type": event_type,
            "rental_id": rental_id,
            "item_id": str(item_id),
        }

    base_payload = {
        "rental_id": str(rental_id),
        "item_id": str(item.id),
        "item_title": item.title,
        "status": data.get("status"),
        "start_date": data.get("start_date"),
        "end_date": data.get("end_date"),
        "owner_comment": data.get("owner_comment"),
    }

    notification_targets: list[tuple[uuid.UUID, str, dict[str, Any]]] = []

    if event_type == "rental.created":
        notification_targets.append(
            (
                item.owner_id,
                "rental_created",
                {
                    **base_payload,
                    "message": "A rental request was created.",
                },
            )
        )

    elif event_type == "rental.approved":
        notification_targets.append(
            (
                renter_id,
                "rental_approved",
                {
                    **base_payload,
                    "message": "Your rental request was approved.",
                },
            )
        )

    elif event_type == "rental.rejected":
        notification_targets.append(
            (
                renter_id,
                "rental_rejected",
                {
                    **base_payload,
                    "message": "Your rental request was rejected.",
                },
            )
        )

    elif event_type == "rental.started":
        notification_targets.append(
            (
                renter_id,
                "rental_started",
                {
                    **base_payload,
                    "message": "Your rental has started.",
                },
            )
        )

    elif event_type == "rental.completed":
        notification_targets.append(
            (
                item.owner_id,
                "rental_completed",
                {
                    **base_payload,
                    "message": "Rental was completed.",
                },
            )
        )

        if renter_id != item.owner_id:
            notification_targets.append(
                (
                    renter_id,
                    "rental_completed",
                    {
                        **base_payload,
                        "message": "Your rental was completed.",
                    },
                )
            )

    elif event_type == "rental.cancelled":
        notification_targets.append(
            (
                item.owner_id,
                "rental_cancelled",
                {
                    **base_payload,
                    "message": "Rental was cancelled.",
                },
            )
        )

    else:
        return {
            "notifications_created": 0,
            "reason": "rental_event_does_not_require_notification",
            "event_type": event_type,
            "rental_id": str(rental_id),
        }

    results = [
        _create_notification_once(
            db,
            user_id=user_id,
            notification_type=notification_type,
            payload=payload,
        )
        for user_id, notification_type, payload in notification_targets
    ]

    return {
        "notifications_created": sum(1 for result in results if result["created"]),
        "reason": "rental_notifications_checked",
        "event_type": event_type,
        "rental_id": str(rental_id),
        "results": results,
    }