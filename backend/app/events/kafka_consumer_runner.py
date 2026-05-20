import asyncio
import contextlib
import json
import logging
from typing import Any

from aiokafka import AIOKafkaConsumer

from app.core.config import settings
from app.core.db import SessionLocal
from app.events.consumer_registry import KafkaConsumerConfig
from app.events.kafka_consumer_handlers import record_consumed_kafka_event

logger = logging.getLogger(__name__)


def _decode_message_value(value: bytes | None) -> dict[str, Any]:
    if value is None:
        return {}

    decoded = value.decode("utf-8")
    payload = json.loads(decoded)

    if isinstance(payload, dict):
        return payload

    return {
        "event_type": "unknown",
        "raw_payload": payload,
    }


def _decode_message_key(key: bytes | None) -> str | None:
    if key is None:
        return None

    return key.decode("utf-8")


def _consumer_group_id(consumer_config: KafkaConsumerConfig) -> str:
    return f"{settings.KAFKA_CONSUMER_GROUP_PREFIX}.{consumer_config.name}"


async def _sleep_or_stop(stop_event: asyncio.Event, timeout_seconds: float) -> None:
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        pass


async def _start_consumer_with_retry(
    consumer: AIOKafkaConsumer,
    *,
    consumer_config: KafkaConsumerConfig,
    stop_event: asyncio.Event,
    max_attempts: int = 30,
    delay_seconds: float = 3.0,
) -> bool:
    attempt = 1

    while not stop_event.is_set() and attempt <= max_attempts:
        try:
            await consumer.start()
            return True
        except asyncio.CancelledError:
            logger.info(
                "Kafka consumer start cancelled: consumer=%s topic=%s",
                consumer_config.name,
                consumer_config.topic,
            )
            return False
        except Exception:
            logger.exception(
                "Kafka consumer start failed: consumer=%s topic=%s attempt=%s/%s",
                consumer_config.name,
                consumer_config.topic,
                attempt,
                max_attempts,
            )

            attempt += 1
            await _sleep_or_stop(stop_event, delay_seconds)

    return False


async def _safe_stop_consumer(
    consumer: AIOKafkaConsumer | None,
    *,
    consumer_config: KafkaConsumerConfig,
) -> None:
    if consumer is None:
        return

    try:
        await asyncio.wait_for(consumer.stop(), timeout=10)
    except asyncio.TimeoutError:
        logger.warning(
            "Kafka consumer stop timed out: consumer=%s topic=%s",
            consumer_config.name,
            consumer_config.topic,
        )
    except asyncio.CancelledError:
        logger.warning(
            "Kafka consumer stop was cancelled: consumer=%s topic=%s",
            consumer_config.name,
            consumer_config.topic,
        )
    except BaseException:
        logger.exception(
            "Kafka consumer stop failed: consumer=%s topic=%s",
            consumer_config.name,
            consumer_config.topic,
        )


async def run_kafka_consumer_loop(
    *,
    consumer_config: KafkaConsumerConfig,
    stop_event: asyncio.Event,
    startup_delay_seconds: float = 0.0,
) -> None:
    consumer: AIOKafkaConsumer | None = None

    if not settings.KAFKA_ENABLED:
        logger.info(
            "Kafka consumer skipped because Kafka is disabled: consumer=%s topic=%s",
            consumer_config.name,
            consumer_config.topic,
        )
        return

    if not settings.KAFKA_CONSUMERS_ENABLED:
        logger.info(
            "Kafka consumer skipped because consumers are disabled: consumer=%s topic=%s",
            consumer_config.name,
            consumer_config.topic,
        )
        return

    try:
        if startup_delay_seconds > 0:
            await _sleep_or_stop(stop_event, startup_delay_seconds)

        if stop_event.is_set():
            return

        consumer = AIOKafkaConsumer(
            consumer_config.topic,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            group_id=_consumer_group_id(consumer_config),
            client_id=f"{settings.KAFKA_CLIENT_ID}-{consumer_config.name}",
            enable_auto_commit=False,
            auto_offset_reset=settings.KAFKA_CONSUMER_AUTO_OFFSET_RESET,
        )

        started = await _start_consumer_with_retry(
            consumer,
            consumer_config=consumer_config,
            stop_event=stop_event,
        )

        if not started:
            logger.error(
                "Kafka consumer was not started: consumer=%s topic=%s",
                consumer_config.name,
                consumer_config.topic,
            )
            return

        logger.info(
            "Kafka consumer started: consumer=%s topic=%s group_id=%s",
            consumer_config.name,
            consumer_config.topic,
            _consumer_group_id(consumer_config),
        )

        while not stop_event.is_set():
            try:
                message_batch = await consumer.getmany(
                    timeout_ms=settings.KAFKA_CONSUMER_POLL_TIMEOUT_MS,
                    max_records=50,
                )

                for _, messages in message_batch.items():
                    for message in messages:
                        if stop_event.is_set():
                            break

                        payload = _decode_message_value(message.value)
                        event_key = _decode_message_key(message.key)

                        db = SessionLocal()
                        try:
                            record_consumed_kafka_event(
                                db,
                                consumer_name=consumer_config.name,
                                topic=message.topic,
                                partition=message.partition,
                                offset=message.offset,
                                event_key=event_key,
                                payload=payload,
                                status="processed",
                            )

                            await consumer.commit()

                        except Exception as exc:
                            logger.exception(
                                "Kafka consumer failed to process event: consumer=%s topic=%s partition=%s offset=%s",
                                consumer_config.name,
                                message.topic,
                                message.partition,
                                message.offset,
                            )

                            with contextlib.suppress(Exception):
                                record_consumed_kafka_event(
                                    db,
                                    consumer_name=consumer_config.name,
                                    topic=message.topic,
                                    partition=message.partition,
                                    offset=message.offset,
                                    event_key=event_key,
                                    payload=payload,
                                    status="failed",
                                    error_message=str(exc),
                                )

                                await consumer.commit()

                        finally:
                            db.close()

            except asyncio.CancelledError:
                logger.info(
                    "Kafka consumer loop cancelled: consumer=%s topic=%s",
                    consumer_config.name,
                    consumer_config.topic,
                )
                break
            except Exception:
                logger.exception(
                    "Kafka consumer loop iteration failed: consumer=%s topic=%s",
                    consumer_config.name,
                    consumer_config.topic,
                )

                await _sleep_or_stop(stop_event, 5)

    finally:
        await _safe_stop_consumer(
            consumer,
            consumer_config=consumer_config,
        )

        logger.info(
            "Kafka consumer stopped: consumer=%s topic=%s",
            consumer_config.name,
            consumer_config.topic,
        )