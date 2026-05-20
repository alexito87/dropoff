import argparse
import asyncio
import random
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.db import SessionLocal
from app.events.outbox import add_event_to_outbox
from app.events.outbox_publisher import publish_pending_outbox_events
from app.events.schemas import EventEnvelope
from app.events.topics import (
    AUDIT_EVENTS_TOPIC,
    CART_EVENTS_TOPIC,
    DELIVERY_EVENTS_TOPIC,
    ITEM_EVENTS_TOPIC,
    MODERATION_EVENTS_TOPIC,
    NOTIFICATION_EVENTS_TOPIC,
    ORDER_EVENTS_TOPIC,
    PAYMENT_EVENTS_TOPIC,
    USER_EVENTS_TOPIC,
)


TOPIC_EVENT_TYPES = {
    USER_EVENTS_TOPIC: [
        "user.created",
        "user.email_verified",
    ],
    ITEM_EVENTS_TOPIC: [
        "item.created",
        "item.updated",
        "item.deleted",
        "item.submitted_for_moderation",
        "item.published",
        "item.rejected",
    ],
    MODERATION_EVENTS_TOPIC: [
        "moderation.item_approved",
        "moderation.item_rejected",
        "moderation.item_needs_changes",
    ],
    CART_EVENTS_TOPIC: [
        "cart.item_added",
        "cart.item_removed",
        "cart.cleared",
        "cart.converted_to_order",
    ],
    ORDER_EVENTS_TOPIC: [
        "order.created",
        "order.paid",
        "order.payment_failed",
        "order.payment_expired",
        "order.completed",
    ],
    PAYMENT_EVENTS_TOPIC: [
        "payment.created",
        "payment.checkout_session_created",
        "payment.succeeded",
        "payment.failed",
        "payment.expired",
    ],
    DELIVERY_EVENTS_TOPIC: [
        "delivery.created",
        "delivery.completed",
        "delivery.return_requested",
        "delivery.cancelled",
    ],
    NOTIFICATION_EVENTS_TOPIC: [
        "notification.created",
    ],
    AUDIT_EVENTS_TOPIC: [
        "audit.domain_event_seeded",
    ],
}


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _money(min_value: int = 500, max_value: int = 100_000) -> int:
    return random.randint(min_value, max_value)


def _base_payload(topic: str, event_type: str, index: int) -> dict[str, Any]:
    return {
        "seed": True,
        "seed_index": index,
        "topic": topic,
        "event_type": event_type,
        "created_at": _now_iso(),
    }


def _user_payload(topic: str, event_type: str, index: int) -> dict[str, Any]:
    return {
        **_base_payload(topic, event_type, index),
        "user_id": str(uuid.uuid4()),
        "email": f"seed-user-{index}@dropoff.local",
        "full_name": f"Seed User {index}",
        "email_verified": event_type == "user.email_verified",
        "is_superuser": False,
    }


def _item_payload(topic: str, event_type: str, index: int) -> dict[str, Any]:
    status_by_event = {
        "item.created": "draft",
        "item.updated": "draft",
        "item.deleted": "deleted",
        "item.submitted_for_moderation": "pending_review",
        "item.published": "published",
        "item.rejected": "rejected",
    }

    return {
        **_base_payload(topic, event_type, index),
        "item_id": str(uuid.uuid4()),
        "owner_id": str(uuid.uuid4()),
        "category_id": str(uuid.uuid4()),
        "title": f"Seed item {index}",
        "description": f"Generated item event #{index}",
        "status": status_by_event.get(event_type, "draft"),
        "daily_price_cents": _money(500, 5_000),
        "deposit_cents": _money(1_000, 20_000),
        "city": random.choice(["Москва", "Санкт-Петербург", "Казань", "Екатеринбург"]),
        "pickup_address": f"Seed street {index}",
        "moderated_by": str(uuid.uuid4()) if event_type in {"item.published", "item.rejected"} else None,
        "moderated_at": _now_iso() if event_type in {"item.published", "item.rejected"} else None,
        "moderation_comment": "Seed moderation comment" if event_type == "item.rejected" else None,
    }


def _moderation_payload(topic: str, event_type: str, index: int) -> dict[str, Any]:
    decision_by_event = {
        "moderation.item_approved": "approved",
        "moderation.item_rejected": "rejected",
        "moderation.item_needs_changes": "needs_changes",
    }

    return {
        **_base_payload(topic, event_type, index),
        "item_id": str(uuid.uuid4()),
        "owner_id": str(uuid.uuid4()),
        "category_id": str(uuid.uuid4()),
        "title": f"Moderated seed item {index}",
        "previous_status": "pending_review",
        "target_status": "published" if event_type == "moderation.item_approved" else "rejected",
        "decision": decision_by_event.get(event_type),
        "moderator_user_id": str(uuid.uuid4()),
        "moderation_comment": None if event_type == "moderation.item_approved" else "Seed moderation decision",
    }


def _cart_payload(topic: str, event_type: str, index: int) -> dict[str, Any]:
    cart_id = uuid.uuid4()
    today = datetime.now(UTC).date()
    rent_start = today + timedelta(days=random.randint(1, 10))
    rent_end = rent_start + timedelta(days=random.randint(1, 7))

    payload = {
        **_base_payload(topic, event_type, index),
        "cart_id": str(cart_id),
        "user_id": str(uuid.uuid4()),
        "status": "converted" if event_type == "cart.converted_to_order" else "active",
    }

    if event_type == "cart.cleared":
        payload["items_count"] = random.randint(1, 5)
        return payload

    if event_type == "cart.converted_to_order":
        payload["order_id"] = str(uuid.uuid4())
        payload["order_status"] = "awaiting_payment"
        payload["total_amount_cents"] = _money(2_000, 150_000)
        return payload

    payload["item"] = {
        "cart_item_id": str(uuid.uuid4()),
        "cart_id": str(cart_id),
        "item_id": str(uuid.uuid4()),
        "rent_start": rent_start.isoformat(),
        "rent_end": rent_end.isoformat(),
        "quantity": random.randint(1, 3),
        "daily_price_cents": _money(500, 5_000),
        "deposit_cents": _money(1_000, 20_000),
        "rent_total_cents": _money(1_000, 50_000),
        "total_deposit_cents": _money(1_000, 20_000),
    }

    return payload


def _order_payload(topic: str, event_type: str, index: int) -> dict[str, Any]:
    total_amount_cents = _money(2_000, 150_000)

    status_by_event = {
        "order.created": "awaiting_payment",
        "order.paid": "paid",
        "order.payment_failed": "payment_failed",
        "order.payment_expired": "payment_expired",
        "order.completed": "completed",
    }

    return {
        **_base_payload(topic, event_type, index),
        "order_id": str(uuid.uuid4()),
        "user_id": str(uuid.uuid4()),
        "cart_id": str(uuid.uuid4()),
        "status": status_by_event.get(event_type, "awaiting_payment"),
        "delivery_method": random.choice(["pickup", "courier_standard"]),
        "payment_method": "stripe_checkout",
        "items_total_cents": total_amount_cents - 1_000,
        "deposit_total_cents": 1_000,
        "delivery_fee_cents": random.choice([0, 1_200]),
        "total_amount_cents": total_amount_cents,
        "payment": {
            "payment_id": str(uuid.uuid4()),
            "status": "paid" if event_type == "order.paid" else "pending",
            "provider": "stripe",
            "payment_method": "stripe_checkout",
            "amount_total_cents": total_amount_cents,
            "currency": "usd",
        },
    }


def _payment_payload(topic: str, event_type: str, index: int) -> dict[str, Any]:
    status_by_event = {
        "payment.created": "pending",
        "payment.checkout_session_created": "checkout_created",
        "payment.succeeded": "paid",
        "payment.failed": "failed",
        "payment.expired": "expired",
    }

    return {
        **_base_payload(topic, event_type, index),
        "payment_id": str(uuid.uuid4()),
        "order_id": str(uuid.uuid4()),
        "payer_user_id": str(uuid.uuid4()),
        "status": status_by_event.get(event_type, "pending"),
        "provider": "stripe",
        "payment_method": "stripe_checkout",
        "amount_total_cents": _money(2_000, 150_000),
        "currency": "usd",
        "stripe_checkout_session_id": f"cs_seed_{uuid.uuid4().hex}",
        "stripe_payment_intent_id": f"pi_seed_{uuid.uuid4().hex}",
    }


def _delivery_payload(topic: str, event_type: str, index: int) -> dict[str, Any]:
    status_by_event = {
        "delivery.created": "in_progress",
        "delivery.completed": "delivered",
        "delivery.return_requested": "return_requested",
        "delivery.cancelled": "cancelled",
    }

    return {
        **_base_payload(topic, event_type, index),
        "delivery_id": str(uuid.uuid4()),
        "order_id": str(uuid.uuid4()),
        "order_item_id": str(uuid.uuid4()),
        "item_id": str(uuid.uuid4()),
        "renter_id": str(uuid.uuid4()),
        "owner_id": str(uuid.uuid4()),
        "status": status_by_event.get(event_type, "in_progress"),
        "courier_name": f"Seed Courier {index}",
        "current_location": random.choice(["Warehouse", "Pickup point", "In transit"]),
        "final_location": "Customer address" if event_type == "delivery.completed" else None,
        "return_reason": "Seed return reason" if event_type == "delivery.return_requested" else None,
    }


def _notification_payload(topic: str, event_type: str, index: int) -> dict[str, Any]:
    return {
        **_base_payload(topic, event_type, index),
        "notification_id": str(uuid.uuid4()),
        "user_id": str(uuid.uuid4()),
        "type": random.choice(
            [
                "item_approved",
                "item_rejected",
                "order_created",
                "payment_success",
                "delivery_started",
            ]
        ),
        "payload": {
            "message": f"Seed notification #{index}",
        },
        "is_read": False,
    }


def _audit_payload(topic: str, event_type: str, index: int) -> dict[str, Any]:
    return {
        **_base_payload(topic, event_type, index),
        "audit_id": str(uuid.uuid4()),
        "message": "Seed domain event generated for Kafka topic validation",
    }


def build_payload(topic: str, event_type: str, index: int) -> dict[str, Any]:
    if topic == USER_EVENTS_TOPIC:
        return _user_payload(topic, event_type, index)

    if topic == ITEM_EVENTS_TOPIC:
        return _item_payload(topic, event_type, index)

    if topic == MODERATION_EVENTS_TOPIC:
        return _moderation_payload(topic, event_type, index)

    if topic == CART_EVENTS_TOPIC:
        return _cart_payload(topic, event_type, index)

    if topic == ORDER_EVENTS_TOPIC:
        return _order_payload(topic, event_type, index)

    if topic == PAYMENT_EVENTS_TOPIC:
        return _payment_payload(topic, event_type, index)

    if topic == DELIVERY_EVENTS_TOPIC:
        return _delivery_payload(topic, event_type, index)

    if topic == NOTIFICATION_EVENTS_TOPIC:
        return _notification_payload(topic, event_type, index)

    return _audit_payload(topic, event_type, index)


def create_seed_events(per_topic: int) -> dict[str, int]:
    db = SessionLocal()
    created_by_topic: dict[str, int] = {}

    try:
        for topic, event_types in TOPIC_EVENT_TYPES.items():
            created_by_topic[topic] = 0

            for index in range(1, per_topic + 1):
                event_type = event_types[(index - 1) % len(event_types)]
                aggregate_id = str(uuid.uuid4())

                event = EventEnvelope(
                    event_type=event_type,
                    producer="kafka-seed-script",
                    aggregate_type=event_type.split(".")[0].title(),
                    aggregate_id=aggregate_id,
                    data=build_payload(topic, event_type, index),
                )

                add_event_to_outbox(
                    db,
                    topic=topic,
                    event=event,
                    key=aggregate_id,
                )

                created_by_topic[topic] += 1

        db.commit()
        return created_by_topic

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def publish_created_events(limit: int) -> dict[str, Any]:
    db = SessionLocal()
    try:
        return await publish_pending_outbox_events(db, limit=limit)
    finally:
        db.close()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Generate seed Kafka events through outbox")
    parser.add_argument("--per-topic", type=int, default=200)
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()

    created_by_topic = create_seed_events(per_topic=args.per_topic)
    total_created = sum(created_by_topic.values())

    print("Created outbox events:")
    for topic, count in created_by_topic.items():
        print(f"- {topic}: {count}")

    print(f"Total created: {total_created}")

    if not args.publish:
        print("Events were created in outbox only. Background publisher should publish them automatically.")
        return

    remaining = total_created
    total_published = 0
    total_failed = 0

    while remaining > 0:
        result = await publish_created_events(limit=min(100, remaining))

        total_published += result["published"]
        total_failed += result["failed"]

        processed = result["published"] + result["failed"]

        if processed == 0:
            break

        remaining -= processed

    print("Publish result:")
    print(f"- published: {total_published}")
    print(f"- failed: {total_failed}")


if __name__ == "__main__":
    asyncio.run(main())