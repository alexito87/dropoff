from dataclasses import dataclass

from app.events.topics import (
    AUDIT_EVENTS_TOPIC,
    CART_EVENTS_TOPIC,
    DELIVERY_EVENTS_TOPIC,
    ITEM_EVENTS_TOPIC,
    MODERATION_EVENTS_TOPIC,
    NOTIFICATION_EVENTS_TOPIC,
    ORDER_EVENTS_TOPIC,
    PAYMENT_EVENTS_TOPIC,
    RENTAL_EVENTS_TOPIC,
    USER_EVENTS_TOPIC,
)


@dataclass(frozen=True)
class KafkaConsumerConfig:
    name: str
    topic: str


KAFKA_CONSUMERS: list[KafkaConsumerConfig] = [
    KafkaConsumerConfig(
        name="users-events-consumer",
        topic=USER_EVENTS_TOPIC,
    ),
    KafkaConsumerConfig(
        name="items-events-consumer",
        topic=ITEM_EVENTS_TOPIC,
    ),
    KafkaConsumerConfig(
        name="moderation-events-consumer",
        topic=MODERATION_EVENTS_TOPIC,
    ),
    KafkaConsumerConfig(
        name="cart-events-consumer",
        topic=CART_EVENTS_TOPIC,
    ),
    KafkaConsumerConfig(
        name="orders-events-consumer",
        topic=ORDER_EVENTS_TOPIC,
    ),
    KafkaConsumerConfig(
        name="payments-events-consumer",
        topic=PAYMENT_EVENTS_TOPIC,
    ),
    KafkaConsumerConfig(
        name="deliveries-events-consumer",
        topic=DELIVERY_EVENTS_TOPIC,
    ),
    KafkaConsumerConfig(
        name="rentals-events-consumer",
        topic=RENTAL_EVENTS_TOPIC,
    ),
    KafkaConsumerConfig(
        name="notifications-events-consumer",
        topic=NOTIFICATION_EVENTS_TOPIC,
    ),
    KafkaConsumerConfig(
        name="audit-events-consumer",
        topic=AUDIT_EVENTS_TOPIC,
    ),
]