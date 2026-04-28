from fastapi import APIRouter

from app.events.kafka_health import check_kafka_connection
from app.events.topics import ALL_TOPICS

router = APIRouter()


@router.get("/health")
async def kafka_health():
    health = await check_kafka_connection()

    return {
        "service": "kafka",
        **health,
        "planned_topics": ALL_TOPICS,
    }