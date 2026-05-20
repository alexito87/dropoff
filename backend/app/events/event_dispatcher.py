import logging
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.events.handlers.audit_handlers import handle_audit_domain_event_seeded
from app.events.handlers.base import (
    EventHandlingResult,
    EventHandlerError,
    failed,
    ignored,
    processed,
    require_event_fields,
)
from app.events.handlers.cart_handlers import (
    handle_cart_cleared,
    handle_cart_converted_to_order,
    handle_cart_item_added,
    handle_cart_item_removed,
)
from app.events.handlers.deliveries_handlers import (
    handle_delivery_cancelled,
    handle_delivery_completed,
    handle_delivery_created,
    handle_delivery_return_requested,
)
from app.events.handlers.items_handlers import (
    handle_item_created,
    handle_item_deleted,
    handle_item_published,
    handle_item_rejected,
    handle_item_submitted_for_moderation,
    handle_item_updated,
)
from app.events.handlers.moderation_handlers import (
    handle_moderation_item_approved,
    handle_moderation_item_needs_changes,
    handle_moderation_item_rejected,
)
from app.events.handlers.notifications_handlers import handle_notification_created
from app.events.handlers.orders_handlers import (
    handle_order_completed,
    handle_order_created,
    handle_order_paid,
    handle_order_payment_expired,
    handle_order_payment_failed,
)
from app.events.handlers.payments_handlers import (
    handle_payment_checkout_session_created,
    handle_payment_created,
    handle_payment_expired,
    handle_payment_failed,
    handle_payment_succeeded,
)
from app.events.handlers.users_handlers import (
    handle_user_created,
    handle_user_email_verified,
)

logger = logging.getLogger(__name__)

EventHandler = Callable[[Session, dict[str, Any]], EventHandlingResult]


EVENT_HANDLERS: dict[str, EventHandler] = {
    "user.created": handle_user_created,
    "user.email_verified": handle_user_email_verified,

    "item.created": handle_item_created,
    "item.updated": handle_item_updated,
    "item.deleted": handle_item_deleted,
    "item.submitted_for_moderation": handle_item_submitted_for_moderation,
    "item.published": handle_item_published,
    "item.rejected": handle_item_rejected,

    "moderation.item_approved": handle_moderation_item_approved,
    "moderation.item_rejected": handle_moderation_item_rejected,
    "moderation.item_needs_changes": handle_moderation_item_needs_changes,

    "cart.item_added": handle_cart_item_added,
    "cart.item_removed": handle_cart_item_removed,
    "cart.cleared": handle_cart_cleared,
    "cart.converted_to_order": handle_cart_converted_to_order,

    "order.created": handle_order_created,
    "order.paid": handle_order_paid,
    "order.payment_failed": handle_order_payment_failed,
    "order.payment_expired": handle_order_payment_expired,
    "order.completed": handle_order_completed,

    "payment.created": handle_payment_created,
    "payment.checkout_session_created": handle_payment_checkout_session_created,
    "payment.succeeded": handle_payment_succeeded,
    "payment.failed": handle_payment_failed,
    "payment.expired": handle_payment_expired,

    "delivery.created": handle_delivery_created,
    "delivery.completed": handle_delivery_completed,
    "delivery.return_requested": handle_delivery_return_requested,
    "delivery.cancelled": handle_delivery_cancelled,

    "notification.created": handle_notification_created,

    "audit.domain_event_seeded": handle_audit_domain_event_seeded,
}


def get_event_handler(event_type: str) -> EventHandler | None:
    return EVENT_HANDLERS.get(event_type)


def dispatch_event(
    db: Session,
    *,
    consumer_name: str,
    topic: str,
    event: dict[str, Any],
) -> EventHandlingResult:
    try:
        require_event_fields(
            event,
            "event_id",
            "event_type",
            "event_version",
            "occurred_at",
            "producer",
            "aggregate_type",
            "aggregate_id",
        )

        event_type = str(event["event_type"])
        handler = get_event_handler(event_type)

        if handler is None:
            logger.warning(
                "No business handler registered for Kafka event: consumer=%s topic=%s event_type=%s event_id=%s",
                consumer_name,
                topic,
                event_type,
                event.get("event_id"),
            )

            return ignored(
                "No business handler registered for event type",
                consumer_name=consumer_name,
                topic=topic,
                event_type=event_type,
                event_id=event.get("event_id"),
            )

        result = handler(db, event)

        logger.info(
            "Kafka event dispatched: consumer=%s topic=%s event_type=%s event_id=%s result=%s",
            consumer_name,
            topic,
            event_type,
            event.get("event_id"),
            result.status,
        )

        return result

    except EventHandlerError as exc:
        logger.warning(
            "Kafka business event validation failed: consumer=%s topic=%s event_type=%s event_id=%s error=%s",
            consumer_name,
            topic,
            event.get("event_type"),
            event.get("event_id"),
            str(exc),
        )

        return failed(
            str(exc),
            consumer_name=consumer_name,
            topic=topic,
            event_type=event.get("event_type"),
            event_id=event.get("event_id"),
        )

    except Exception as exc:
        logger.exception(
            "Kafka business event dispatch failed: consumer=%s topic=%s event_type=%s event_id=%s",
            consumer_name,
            topic,
            event.get("event_type"),
            event.get("event_id"),
        )

        return failed(
            str(exc),
            consumer_name=consumer_name,
            topic=topic,
            event_type=event.get("event_type"),
            event_id=event.get("event_id"),
        )


def list_registered_event_types() -> list[str]:
    return sorted(EVENT_HANDLERS.keys())


def is_event_type_registered(event_type: str) -> bool:
    return event_type in EVENT_HANDLERS


def register_event_handler(event_type: str, handler: EventHandler) -> None:
    if event_type in EVENT_HANDLERS:
        raise ValueError(f"Handler already registered for event type: {event_type}")

    EVENT_HANDLERS[event_type] = handler


def dispatch_event_without_business_side_effects(
    db: Session,
    *,
    consumer_name: str,
    topic: str,
    event: dict[str, Any],
) -> EventHandlingResult:
    """
    Safe mode for tests and diagnostics.

    This validates that the event has a known handler,
    but intentionally does not execute target-context writes.
    """
    require_event_fields(event, "event_type")

    event_type = str(event["event_type"])

    if event_type not in EVENT_HANDLERS:
        return ignored(
            "No business handler registered for event type",
            consumer_name=consumer_name,
            topic=topic,
            event_type=event_type,
        )

    return processed(
        "Business handler is registered",
        consumer_name=consumer_name,
        topic=topic,
        event_type=event_type,
    )