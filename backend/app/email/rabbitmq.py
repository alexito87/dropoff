import json
import logging
from typing import Any

import pika

from app.core.config import settings

logger = logging.getLogger(__name__)


def _connection_parameters() -> pika.URLParameters:
    return pika.URLParameters(settings.RABBITMQ_URL)


def declare_email_topology(channel: pika.adapters.blocking_connection.BlockingChannel) -> None:
    channel.exchange_declare(
        exchange=settings.RABBITMQ_EMAIL_EXCHANGE,
        exchange_type="direct",
        durable=True,
    )

    channel.queue_declare(
        queue=settings.RABBITMQ_EMAIL_QUEUE,
        durable=True,
        arguments={
            "x-dead-letter-exchange": settings.RABBITMQ_EMAIL_EXCHANGE,
            "x-dead-letter-routing-key": settings.RABBITMQ_EMAIL_DLQ_ROUTING_KEY,
        },
    )

    channel.queue_declare(
        queue=settings.RABBITMQ_EMAIL_RETRY_QUEUE,
        durable=True,
        arguments={
            "x-message-ttl": settings.RABBITMQ_EMAIL_RETRY_DELAY_MS,
            "x-dead-letter-exchange": settings.RABBITMQ_EMAIL_EXCHANGE,
            "x-dead-letter-routing-key": settings.RABBITMQ_EMAIL_ROUTING_KEY,
        },
    )

    channel.queue_declare(
        queue=settings.RABBITMQ_EMAIL_DLQ,
        durable=True,
    )

    channel.queue_bind(
        queue=settings.RABBITMQ_EMAIL_QUEUE,
        exchange=settings.RABBITMQ_EMAIL_EXCHANGE,
        routing_key=settings.RABBITMQ_EMAIL_ROUTING_KEY,
    )

    channel.queue_bind(
        queue=settings.RABBITMQ_EMAIL_RETRY_QUEUE,
        exchange=settings.RABBITMQ_EMAIL_EXCHANGE,
        routing_key=settings.RABBITMQ_EMAIL_RETRY_ROUTING_KEY,
    )

    channel.queue_bind(
        queue=settings.RABBITMQ_EMAIL_DLQ,
        exchange=settings.RABBITMQ_EMAIL_EXCHANGE,
        routing_key=settings.RABBITMQ_EMAIL_DLQ_ROUTING_KEY,
    )


def publish_email_message(
    message: dict[str, Any],
    *,
    routing_key: str | None = None,
    headers: dict[str, Any] | None = None,
) -> None:
    if not settings.RABBITMQ_ENABLED:
        logger.info(
            "RabbitMQ is disabled. Email message was not published: message_type=%s message_id=%s",
            message.get("message_type"),
            message.get("message_id"),
        )
        return

    routing_key = routing_key or settings.RABBITMQ_EMAIL_ROUTING_KEY
    headers = headers or {}

    connection = pika.BlockingConnection(_connection_parameters())

    try:
        channel = connection.channel()
        declare_email_topology(channel)

        channel.basic_publish(
            exchange=settings.RABBITMQ_EMAIL_EXCHANGE,
            routing_key=routing_key,
            body=json.dumps(message, ensure_ascii=False).encode("utf-8"),
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=2,
                message_id=str(message.get("message_id") or ""),
                type=str(message.get("message_type") or "email.send"),
                correlation_id=str(message.get("correlation_id") or ""),
                headers=headers,
            ),
            mandatory=False,
        )

        logger.info(
            "Email message published to RabbitMQ: message_type=%s message_id=%s routing_key=%s",
            message.get("message_type"),
            message.get("message_id"),
            routing_key,
        )

    finally:
        connection.close()


def publish_email_retry_message(
    message: dict[str, Any],
    *,
    attempts: int,
    error_message: str,
) -> None:
    publish_email_message(
        message,
        routing_key=settings.RABBITMQ_EMAIL_RETRY_ROUTING_KEY,
        headers={
            "x-retry-count": attempts,
            "x-last-error": error_message,
        },
    )


def publish_email_dlq_message(
    message: dict[str, Any],
    *,
    attempts: int,
    error_message: str,
) -> None:
    publish_email_message(
        message,
        routing_key=settings.RABBITMQ_EMAIL_DLQ_ROUTING_KEY,
        headers={
            "x-retry-count": attempts,
            "x-last-error": error_message,
        },
    )