from aiokafka import AIOKafkaProducer

from app.core.config import settings
from app.events.topics import HEALTHCHECK_TOPIC


async def check_kafka_connection() -> dict:
    if not settings.KAFKA_ENABLED:
        return {
            "enabled": False,
            "status": "disabled",
            "bootstrap_servers": settings.KAFKA_BOOTSTRAP_SERVERS,
        }

    producer = AIOKafkaProducer(
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        client_id=f"{settings.KAFKA_CLIENT_ID}-health-check",
    )

    try:
        await producer.start()
        partitions = await producer.partitions_for(HEALTHCHECK_TOPIC)

        return {
            "enabled": True,
            "status": "ok",
            "bootstrap_servers": settings.KAFKA_BOOTSTRAP_SERVERS,
            "healthcheck_topic": HEALTHCHECK_TOPIC,
            "partitions": sorted(list(partitions or [])),
        }
    except Exception as exc:
        return {
            "enabled": True,
            "status": "error",
            "bootstrap_servers": settings.KAFKA_BOOTSTRAP_SERVERS,
            "healthcheck_topic": HEALTHCHECK_TOPIC,
            "error": str(exc),
        }
    finally:
        await producer.stop()