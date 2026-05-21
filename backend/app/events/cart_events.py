from sqlalchemy.orm import Session

from app.events.outbox import add_event_to_outbox
from app.events.schemas import EventEnvelope
from app.events.topics import CART_EVENTS_TOPIC


def _cart_payload(cart) -> dict:
    return {
        "cart_id": str(cart.id),
        "user_id": str(cart.user_id),
        "status": cart.status,
        "created_at": cart.created_at.isoformat() if cart.created_at else None,
        "updated_at": cart.updated_at.isoformat() if cart.updated_at else None,
    }


def _cart_item_payload(cart_item) -> dict:
    return {
        "cart_item_id": str(cart_item.id),
        "cart_id": str(cart_item.cart_id),
        "item_id": str(cart_item.item_id),
        "rent_start": cart_item.rent_start.isoformat(),
        "rent_end": cart_item.rent_end.isoformat(),
        "quantity": cart_item.quantity,
        "daily_price_cents": cart_item.daily_price_cents,
        "deposit_cents": cart_item.deposit_cents,
        "rent_total_cents": cart_item.rent_total_cents,
        "total_deposit_cents": cart_item.total_deposit_cents,
        "created_at": cart_item.created_at.isoformat() if cart_item.created_at else None,
        "updated_at": cart_item.updated_at.isoformat() if cart_item.updated_at else None,
    }


def add_cart_item_added_event_to_outbox(
    db: Session,
    *,
    cart,
    cart_item,
    user_id,
) -> None:
    event = EventEnvelope(
        event_type="cart.item_added",
        producer="cart-endpoint",
        aggregate_type="Cart",
        aggregate_id=str(cart.id),
        data={
            **_cart_payload(cart),
            "user_id": str(user_id),
            "item": _cart_item_payload(cart_item),
        },
    )

    add_event_to_outbox(
        db,
        topic=CART_EVENTS_TOPIC,
        event=event,
        key=str(cart.id),
    )


def add_cart_item_removed_event_to_outbox(
    db: Session,
    *,
    cart,
    cart_item,
    user_id,
) -> None:
    event = EventEnvelope(
        event_type="cart.item_removed",
        producer="cart-endpoint",
        aggregate_type="Cart",
        aggregate_id=str(cart.id),
        data={
            **_cart_payload(cart),
            "user_id": str(user_id),
            "item": _cart_item_payload(cart_item),
        },
    )

    add_event_to_outbox(
        db,
        topic=CART_EVENTS_TOPIC,
        event=event,
        key=str(cart.id),
    )


def add_cart_cleared_event_to_outbox(
    db: Session,
    *,
    cart,
    user_id,
    items_count: int,
) -> None:
    event = EventEnvelope(
        event_type="cart.cleared",
        producer="cart-endpoint",
        aggregate_type="Cart",
        aggregate_id=str(cart.id),
        data={
            **_cart_payload(cart),
            "user_id": str(user_id),
            "items_count": items_count,
        },
    )

    add_event_to_outbox(
        db,
        topic=CART_EVENTS_TOPIC,
        event=event,
        key=str(cart.id),
    )


def add_cart_checkout_requested_event_to_outbox(
    db: Session,
    *,
    cart,
    user_id,
    delivery_method: str,
    payment_method: str,
) -> None:
    event = EventEnvelope(
        event_type="cart.checkout_requested",
        producer="orders-endpoint",
        aggregate_type="Cart",
        aggregate_id=str(cart.id),
        data={
            **_cart_payload(cart),
            "user_id": str(user_id),
            "delivery_method": delivery_method,
            "payment_method": payment_method,
        },
    )

    add_event_to_outbox(
        db,
        topic=CART_EVENTS_TOPIC,
        event=event,
        key=str(cart.id),
    )


def add_cart_converted_to_order_event_to_outbox(
    db: Session,
    *,
    cart,
    order,
    user_id,
) -> None:
    event = EventEnvelope(
        event_type="cart.converted_to_order",
        producer="orders-consumer",
        aggregate_type="Cart",
        aggregate_id=str(cart.id),
        data={
            **_cart_payload(cart),
            "user_id": str(user_id),
            "order_id": str(order.id),
            "order_status": order.status,
            "total_amount_cents": order.total_amount_cents,
        },
    )

    add_event_to_outbox(
        db,
        topic=CART_EVENTS_TOPIC,
        event=event,
        key=str(cart.id),
    )