from sqlalchemy.orm import Session

from app.events.outbox import add_event_to_outbox
from app.events.schemas import EventEnvelope
from app.events.topics import ORDER_EVENTS_TOPIC


def add_order_created_event_to_outbox(
    db: Session,
    *,
    order,
    payment,
    cart,
    cart_items,
    user_id,
) -> None:
    order_created_event = EventEnvelope(
        event_type="order.created",
        producer="orders-endpoint",
        aggregate_type="Order",
        aggregate_id=str(order.id),
        data={
            "order_id": str(order.id),
            "user_id": str(user_id),
            "cart_id": str(cart.id),
            "status": order.status,
            "delivery_method": order.delivery_method,
            "payment_method": order.payment_method,
            "items_total_cents": order.items_total_cents,
            "deposit_total_cents": order.deposit_total_cents,
            "delivery_fee_cents": order.delivery_fee_cents,
            "total_amount_cents": order.total_amount_cents,
            "payment": {
                "payment_id": str(payment.id),
                "status": payment.status,
                "provider": payment.provider,
                "payment_method": payment.payment_method,
                "amount_total_cents": payment.amount_total_cents,
                "currency": payment.currency,
            },
            "items": [
                {
                    "item_id": str(cart_item.item_id),
                    "rent_start": cart_item.rent_start.isoformat(),
                    "rent_end": cart_item.rent_end.isoformat(),
                    "quantity": cart_item.quantity,
                    "daily_price_cents": cart_item.daily_price_cents,
                    "deposit_cents": cart_item.deposit_cents,
                    "rent_total_cents": cart_item.rent_total_cents,
                    "total_deposit_cents": cart_item.total_deposit_cents,
                }
                for cart_item in cart_items
            ],
        },
    )

    add_event_to_outbox(
        db,
        topic=ORDER_EVENTS_TOPIC,
        event=order_created_event,
        key=str(order.id),
    )