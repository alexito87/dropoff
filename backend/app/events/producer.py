import json
from typing import Any

from aiokafka import AIOKafkaProducer

from app.core.config import settings
from app.events.schemas import EventEnvelope


class KafkaEventProducer:
    def __init__(self) -> None:
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        if not settings.KAFKA_ENABLED:
            return

        if self._producer is not None:
            return

        self._producer = AIOKafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            client_id=settings.KAFKA_CLIENT_ID,
            value_serializer=lambda value: json.dumps(value).encode("utf-8"),
            key_serializer=lambda value: value.encode("utf-8") if value else None,
        )

        await self._producer.start()

    async def stop(self) -> None:
        if self._producer is None:
            return

        await self._producer.stop()
        self._producer = None

    async def publish(
        self,
        topic: str,
        event: EventEnvelope,
        key: str | None = None,
    ) -> dict[str, Any]:
        if not settings.KAFKA_ENABLED:
            return {
                "published": False,
                "reason": "kafka_disabled",
                "topic": topic,
                "event_id": str(event.event_id),
            }

        if self._producer is None:
            await self.start()

        if self._producer is None:
            raise RuntimeError("Kafka producer is not initialized")

        metadata = await self._producer.send_and_wait(
            topic=topic,
            key=key,
            value=event.to_kafka_dict(),
        )

        return {
            "published": True,
            "topic": metadata.topic,
            "partition": metadata.partition,
            "offset": metadata.offset,
            "event_id": str(event.event_id),
            "event_type": event.event_type,
        }


kafka_event_producer = KafkaEventProducer()