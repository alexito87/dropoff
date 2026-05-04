from uuid import uuid4

from fastapi import APIRouter

from app.events.kafka_health import check_kafka_connection
from app.events.producer import kafka_event_producer
from app.events.schemas import EventEnvelope
from app.events.topics import ALL_TOPICS, AUDIT_EVENTS_TOPIC

router = APIRouter()


@router.get("/health")
async def kafka_health():
    health = await check_kafka_connection()

    return {
        "service": "kafka",
        **health,
        "planned_topics": ALL_TOPICS,
    }


@router.post("/test-event")
async def publish_test_event():
    aggregate_id = str(uuid4())

    event = EventEnvelope(
        event_type="audit.test_event_published",
        producer="dropoff-backend",
        aggregate_type="KafkaTestEvent",
        aggregate_id=aggregate_id,
        data={
            "message": "Kafka test event from DropOff backend",
            "source": "POST /api/v1/kafka/test-event",
        },
    )

    publish_result = await kafka_event_producer.publish(
        topic=AUDIT_EVENTS_TOPIC,
        event=event,
        key=aggregate_id,
    )

    return {
        "service": "kafka",
        "status": "published",
        "result": publish_result,
        "event": event.to_kafka_dict(),
    }