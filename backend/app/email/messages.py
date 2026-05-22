import uuid
from datetime import datetime, timezone
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_email_send_message(
    *,
    notification_id: str,
    recipient_email: str,
    recipient_user_id: str,
    notification_type: str,
    payload: dict[str, Any],
    correlation_id: str | None = None,
    causation_id: str | None = None,
) -> dict[str, Any]:
    return {
        "message_id": str(uuid.uuid4()),
        "message_type": "email.send",
        "message_version": 1,
        "created_at": _now_iso(),
        "producer": "notifications-consumer",
        "correlation_id": correlation_id or str(uuid.uuid4()),
        "causation_id": causation_id,
        "data": {
            "notification_id": notification_id,
            "recipient_email": recipient_email,
            "recipient_user_id": recipient_user_id,
            "template_code": notification_type,
            "template_data": payload or {},
        },
    }