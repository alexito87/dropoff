import json
import logging
import signal
import sys
from typing import Any

import pika

from app.core.config import settings
from app.email.rabbitmq import (
    declare_email_topology,
    publish_email_dlq_message,
    publish_email_retry_message,
)
from app.email.smtp_sender import send_email
from app.email.templates import render_email

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

should_stop = False


def _handle_stop_signal(signum, frame) -> None:
    global should_stop
    should_stop = True
    logger.info("Email worker stop signal received: signal=%s", signum)


def _message_headers(properties: pika.BasicProperties | None) -> dict[str, Any]:
    if not properties or not properties.headers:
        return {}

    return dict(properties.headers)


def _retry_count(properties: pika.BasicProperties | None) -> int:
    headers = _message_headers(properties)
    value = headers.get("x-retry-count", 0)

    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _decode_message(body: bytes) -> dict[str, Any]:
    payload = json.loads(body.decode("utf-8"))

    if not isinstance(payload, dict):
        raise ValueError("RabbitMQ email message body must be a JSON object")

    return payload


def _handle_email_message(message: dict[str, Any]) -> None:
    if message.get("message_type") != "email.send":
        raise ValueError(f"Unsupported message_type: {message.get('message_type')}")

    data = message.get("data")

    if not isinstance(data, dict):
        raise ValueError("Email message data must be a JSON object")

    recipient_email = data.get("recipient_email")
    template_code = data.get("template_code")
    template_data = data.get("template_data") or {}

    if not recipient_email:
        raise ValueError("Missing recipient_email")

    if not template_code:
        raise ValueError("Missing template_code")

    subject, body = render_email(
        template_code=str(template_code),
        template_data=template_data,
    )

    send_email(
        to_email=str(recipient_email),
        subject=subject,
        body=body,
    )


def main() -> None:
    signal.signal(signal.SIGTERM, _handle_stop_signal)
    signal.signal(signal.SIGINT, _handle_stop_signal)

    logger.info("Email worker starting")

    connection = pika.BlockingConnection(pika.URLParameters(settings.RABBITMQ_URL))
    channel = connection.channel()

    declare_email_topology(channel)
    channel.basic_qos(prefetch_count=1)

    def callback(ch, method, properties, body) -> None:
        attempts = _retry_count(properties)
        message: dict[str, Any] | None = None

        try:
            message = _decode_message(body)
            _handle_email_message(message)

            ch.basic_ack(delivery_tag=method.delivery_tag)

            logger.info(
                "Email message processed successfully: message_id=%s recipient=%s",
                message.get("message_id"),
                (message.get("data") or {}).get("recipient_email"),
            )

        except Exception as exc:
            error_message = str(exc)
            attempts += 1

            logger.exception(
                "Email message processing failed: attempts=%s max_attempts=%s error=%s",
                attempts,
                settings.RABBITMQ_EMAIL_MAX_ATTEMPTS,
                error_message,
            )

            try:
                if message is None:
                    message = {
                        "message_id": None,
                        "message_type": "email.send",
                        "message_version": 1,
                        "producer": "email-worker",
                        "data": {
                            "raw_body": body.decode("utf-8", errors="replace"),
                        },
                    }

                if attempts >= settings.RABBITMQ_EMAIL_MAX_ATTEMPTS:
                    publish_email_dlq_message(
                        message,
                        attempts=attempts,
                        error_message=error_message,
                    )
                    logger.error(
                        "Email message moved to DLQ: message_id=%s",
                        message.get("message_id"),
                    )
                else:
                    publish_email_retry_message(
                        message,
                        attempts=attempts,
                        error_message=error_message,
                    )
                    logger.info(
                        "Email message moved to retry queue: message_id=%s attempts=%s",
                        message.get("message_id"),
                        attempts,
                    )

                ch.basic_ack(delivery_tag=method.delivery_tag)

            except Exception:
                logger.exception(
                    "Failed to route failed email message. Message was not acknowledged."
                )
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

        if should_stop:
            ch.stop_consuming()

    channel.basic_consume(
        queue=settings.RABBITMQ_EMAIL_QUEUE,
        on_message_callback=callback,
        auto_ack=False,
    )

    logger.info(
        "Email worker started. Waiting for messages: queue=%s",
        settings.RABBITMQ_EMAIL_QUEUE,
    )

    try:
        channel.start_consuming()
    finally:
        logger.info("Email worker stopping")
        try:
            channel.close()
        except Exception:
            pass
        connection.close()
        logger.info("Email worker stopped")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)