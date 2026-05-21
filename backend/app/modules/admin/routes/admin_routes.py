from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.admin import require_admin
from app.models.consumed_kafka_event import ConsumedKafkaEvent
from app.models.dead_letter_kafka_event import DeadLetterKafkaEvent
from app.models.event_projection import (
    AuditDomainEventProjection,
    CatalogItemProjection,
    DeliveriesOrderProjection,
    ModerationItemProjection,
    NotificationsUserProjection,
    OrdersCartProjection,
    OrdersDeliveryProjection,
    OrdersItemProjection,
    OrdersPaymentProjection,
    PaymentsOrderProjection,
)
from app.models.outbox_event import OutboxEvent
from app.models.processed_domain_event import ProcessedDomainEvent
from app.modules.catalog.models.category import Category
from app.modules.deliveries.models.delivery import Delivery
from app.modules.items.models.item import Item
from app.modules.items.models.item_image import ItemImage
from app.modules.notifications.models.notification import Notification
from app.modules.orders.models.cart import Cart, CartItem
from app.modules.orders.models.order import Order, OrderItem
from app.modules.payments.models.payment import (
    Payment,
    PaymentTransaction,
    StripeCheckoutSession,
    StripePaymentIntent,
)
from app.modules.rentals.models.rental import Rental
from app.modules.users.models.user import User

router = APIRouter()


def _count(db: Session, model) -> int:
    return int(db.query(func.count(model.id)).scalar() or 0)


def _count_by_field(db: Session, model, field_name: str) -> dict[str, int]:
    field = getattr(model, field_name)

    rows = (
        db.query(field, func.count(model.id))
        .group_by(field)
        .order_by(field.asc())
        .all()
    )

    return {
        str(value): int(count)
        for value, count in rows
    }


def _count_by_two_fields(
    db: Session,
    model,
    first_field_name: str,
    second_field_name: str,
) -> dict[str, dict[str, int]]:
    first_field = getattr(model, first_field_name)
    second_field = getattr(model, second_field_name)

    rows = (
        db.query(first_field, second_field, func.count(model.id))
        .group_by(first_field, second_field)
        .order_by(first_field.asc(), second_field.asc())
        .all()
    )

    result: dict[str, dict[str, int]] = {}

    for first_value, second_value, count in rows:
        first_key = str(first_value)
        second_key = str(second_value)

        result.setdefault(first_key, {})
        result[first_key][second_key] = int(count)

    return result


def _projection_summary(db: Session) -> dict[str, Any]:
    projection_models = {
        "catalog_item_projections": CatalogItemProjection,
        "moderation_item_projections": ModerationItemProjection,
        "orders_item_projections": OrdersItemProjection,
        "orders_cart_projections": OrdersCartProjection,
        "payments_order_projections": PaymentsOrderProjection,
        "deliveries_order_projections": DeliveriesOrderProjection,
        "orders_payment_projections": OrdersPaymentProjection,
        "orders_delivery_projections": OrdersDeliveryProjection,
        "notifications_user_projections": NotificationsUserProjection,
        "audit_domain_event_projections": AuditDomainEventProjection,
    }

    tables: dict[str, int] = {}
    total = 0

    for table_name, model in projection_models.items():
        rows_count = _count(db, model)
        tables[table_name] = rows_count
        total += rows_count

    return {
        "total": total,
        "tables": tables,
    }


def _business_entities_summary(db: Session) -> dict[str, Any]:
    return {
        "users": {
            "total": _count(db, User),
            "by_is_active": _count_by_field(db, User, "is_active"),
            "by_is_superuser": _count_by_field(db, User, "is_superuser"),
        },
        "categories": {
            "total": _count(db, Category),
        },
        "items": {
            "total": _count(db, Item),
            "by_status": _count_by_field(db, Item, "status"),
            "images_total": _count(db, ItemImage),
        },
        "carts": {
            "total": _count(db, Cart),
            "by_status": _count_by_field(db, Cart, "status"),
            "cart_items_total": _count(db, CartItem),
        },
        "orders": {
            "total": _count(db, Order),
            "by_status": _count_by_field(db, Order, "status"),
            "order_items_total": _count(db, OrderItem),
            "order_items_by_status": _count_by_field(db, OrderItem, "status"),
        },
        "payments": {
            "total": _count(db, Payment),
            "by_status": _count_by_field(db, Payment, "status"),
            "transactions_total": _count(db, PaymentTransaction),
            "checkout_sessions_total": _count(db, StripeCheckoutSession),
            "payment_intents_total": _count(db, StripePaymentIntent),
        },
        "rentals": {
            "total": _count(db, Rental),
            "by_status": _count_by_field(db, Rental, "status"),
        },
        "deliveries": {
            "total": _count(db, Delivery),
            "by_status": _count_by_field(db, Delivery, "status"),
        },
        "notifications": {
            "total": _count(db, Notification),
            "by_is_read": _count_by_field(db, Notification, "is_read"),
            "by_type": _count_by_field(db, Notification, "type"),
        },
    }


def _eda_summary(db: Session) -> dict[str, Any]:
    return {
        "outbox": {
            "total": _count(db, OutboxEvent),
            "by_status": _count_by_field(db, OutboxEvent, "status"),
            "by_topic_status": _count_by_two_fields(db, OutboxEvent, "topic", "status"),
        },
        "consumed_kafka_events": {
            "total": _count(db, ConsumedKafkaEvent),
            "by_status": _count_by_field(db, ConsumedKafkaEvent, "status"),
            "by_topic_status": _count_by_two_fields(db, ConsumedKafkaEvent, "topic", "status"),
        },
        "processed_domain_events": {
            "total": _count(db, ProcessedDomainEvent),
            "by_handling_status": _count_by_field(db, ProcessedDomainEvent, "handling_status"),
            "by_event_type_status": _count_by_two_fields(
                db,
                ProcessedDomainEvent,
                "event_type",
                "handling_status",
            ),
        },
        "dead_letter_kafka_events": {
            "total": _count(db, DeadLetterKafkaEvent),
            "by_status": _count_by_field(db, DeadLetterKafkaEvent, "status"),
            "by_error_type": _count_by_field(db, DeadLetterKafkaEvent, "error_type"),
            "by_topic_status": _count_by_two_fields(db, DeadLetterKafkaEvent, "topic", "status"),
        },
        "projections": _projection_summary(db),
    }


@router.get("/summary")
def read_admin_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(current_user)

    return {
        "service": "admin-summary",
        "business_entities": _business_entities_summary(db),
        "eda": _eda_summary(db),
    }


@router.get("/coverage")
def read_admin_coverage(
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    return {
        "service": "admin-coverage",
        "rule": "Admin users should be able to manage every business entity and operational entity.",
        "covered": {
            "users": {
                "read_all": "GET /api/v1/users/admin",
                "read_one": "GET /api/v1/users/{user_id}",
                "update": "PATCH /api/v1/users/{user_id}",
                "activate": "POST /api/v1/users/{user_id}/activate",
                "deactivate": "POST /api/v1/users/{user_id}/deactivate",
            },
            "categories": {
                "read_all": "GET /api/v1/catalog/admin/categories",
                "create": "POST /api/v1/catalog/admin/categories",
                "update": "PATCH /api/v1/catalog/admin/categories/{category_id}",
                "delete": "DELETE /api/v1/catalog/admin/categories/{category_id}",
            },
            "items": {
                "read_all": "GET /api/v1/items/admin",
                "read_one": "GET /api/v1/items/{item_id}",
                "update": "PATCH /api/v1/items/{item_id}",
                "delete": "DELETE /api/v1/items/{item_id}",
                "submit_for_moderation": "POST /api/v1/items/{item_id}/submit-for-moderation",
                "upload_image": "POST /api/v1/items/{item_id}/images",
                "replace_image": "PUT /api/v1/items/{item_id}/images/{image_id}/replace",
                "delete_image": "DELETE /api/v1/items/{item_id}/images/{image_id}",
            },
            "orders": {
                "read_all": "GET /api/v1/orders/admin",
                "read_one": "GET /api/v1/orders/{order_id}",
                "checkout_session": "POST /api/v1/orders/{order_id}/checkout-session",
                "stripe_confirm": "POST /api/v1/orders/{order_id}/stripe/confirm",
                "sandbox_pay": "POST /api/v1/orders/{order_id}/sandbox-pay",
            },
            "payments": {
                "read_all": "GET /api/v1/payments/admin",
                "read_one": "GET /api/v1/payments/{payment_id}",
                "read_by_order": "GET /api/v1/payments/order/{order_id}",
            },
            "rentals": {
                "read_all": "GET /api/v1/rentals/admin",
                "read_one": "GET /api/v1/rentals/{rental_id}",
                "approve": "POST /api/v1/rentals/{rental_id}/approve",
                "reject": "POST /api/v1/rentals/{rental_id}/reject",
                "start": "POST /api/v1/rentals/{rental_id}/start",
                "complete": "POST /api/v1/rentals/{rental_id}/complete",
                "cancel": "POST /api/v1/rentals/{rental_id}/cancel",
            },
            "deliveries": {
                "read_all": "GET /api/v1/deliveries/admin",
                "read_one": "GET /api/v1/deliveries/{delivery_id}",
                "create": "POST /api/v1/deliveries",
                "complete": "POST /api/v1/deliveries/{delivery_id}/complete",
                "return_request": "POST /api/v1/deliveries/{delivery_id}/return-request",
            },
            "carts": {
                "read_all_active": "GET /api/v1/cart/admin",
                "read_by_cart_id": "GET /api/v1/cart/admin/{cart_id}",
                "read_user_active_cart": "GET /api/v1/cart/admin/users/{user_id}",
                "add_item_to_user_cart": "POST /api/v1/cart/admin/users/{user_id}/items",
                "clear_cart": "DELETE /api/v1/cart/admin/{cart_id}",
                "remove_cart_item": "DELETE /api/v1/cart/items/{cart_item_id}",
            },
            "notifications": {
                "read_all": "GET /api/v1/notifications/admin",
                "read_by_user": "GET /api/v1/notifications/admin/users/{user_id}",
                "create": "POST /api/v1/notifications/admin",
                "mark_any_read": "POST /api/v1/notifications/admin/{notification_id}/read",
                "delete": "DELETE /api/v1/notifications/admin/{notification_id}",
            },
            "kafka_monitoring": {
                "health": "GET /api/v1/kafka/health",
                "outbox_summary": "GET /api/v1/kafka/outbox/summary",
                "outbox_events": "GET /api/v1/kafka/outbox/events",
                "consumers_summary": "GET /api/v1/kafka/consumers/summary",
                "consumers_events": "GET /api/v1/kafka/consumers/events",
                "projections_summary": "GET /api/v1/kafka/projections/summary",
                "projections_events": "GET /api/v1/kafka/projections/events",
                "dlq_summary": "GET /api/v1/kafka/dlq/summary",
                "dlq_events": "GET /api/v1/kafka/dlq/events",
            },
        },
        "not_fully_covered_yet": {
            "auth_email_verification": [
                "Admin manual verify user email",
                "Admin resend verification",
            ],
            "moderation": [
                "Admin list pending moderation items",
                "Admin approve item",
                "Admin reject item",
                "Admin request item changes",
            ],
            "catalog_admin_view": [
                "Admin catalog search by all statuses",
                "Admin catalog details for non-published items",
            ],
            "orders_force_actions": [
                "Admin cancel order",
                "Admin force status transition",
                "Admin mark payment failed/expired manually",
            ],
            "payments_force_actions": [
                "Admin mark payment failed",
                "Admin mark payment refunded",
                "Admin expire payment",
                "Admin retry checkout",
            ],
            "deliveries_force_actions": [
                "Admin cancel delivery",
                "Admin force complete delivery",
            ],
            "rentals_force_actions": [
                "Admin force status transition",
                "Admin force cancel active/completed rental",
            ],
            "carts_history": [
                "Admin read converted carts",
                "Admin read all carts by status",
            ],
            "dlq_manual_actions": [
                "Admin mark DLQ event resolved",
                "Admin mark DLQ event ignored",
                "Admin retry DLQ event",
            ],
        },
        "recommended_next_pack": "Admin force actions for DLQ, Orders, Payments, Deliveries and Rentals.",
    }