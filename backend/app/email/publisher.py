import logging
from typing import Any

from sqlalchemy.orm import Session

from app.email.messages import build_email_send_message
from app.email.rabbitmq import publish_email_message
from app.modules.users.models.user import User

logger = logging.getLogger(__name__)


def enqueue_notification_email(
    db: Session,
    *,
    notification_id: str,
    user_id: str,
    notification_type: str,
    payload: dict[str, Any],
    correlation_id: str | None = None,
    causation_id: str | None = None,
) -> dict[str, Any]:
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return {
            "email_queued": False,
            "reason": "user_not_found",
            "user_id": str(user_id),
            "notification_id": str(notification_id),
        }

    if not user.email:
        return {
            "email_queued": False,
            "reason": "user_email_not_found",
            "user_id": str(user_id),
            "notification_id": str(notification_id),
        }

    message = build_email_send_message(
        notification_id=str(notification_id),
        recipient_email=str(user.email),
        recipient_user_id=str(user.id),
        notification_type=str(notification_type),
        payload=payload or {},
        correlation_id=correlation_id,
        causation_id=causation_id,
    )

    publish_email_message(message)

    logger.info(
        "Notification email queued: notification_id=%s user_id=%s email=%s message_id=%s",
        notification_id,
        user_id,
        user.email,
        message["message_id"],
    )

    return {
        "email_queued": True,
        "reason": "email_message_published_to_rabbitmq",
        "notification_id": str(notification_id),
        "user_id": str(user_id),
        "recipient_email": str(user.email),
        "message_id": message["message_id"],
    }