from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.events.kafka_health import check_kafka_connection
from app.events.outbox import add_event_to_outbox
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


@router.post("/test-outbox-event")
def create_test_outbox_event(db: Session = Depends(get_db)):
    aggregate_id = str(uuid4())

    event = EventEnvelope(
        event_type="audit.test_outbox_event_created",
        producer="dropoff-backend",
        aggregate_type="OutboxTestEvent",
        aggregate_id=aggregate_id,
        data={
            "message": "Outbox test event from DropOff backend",
            "source": "POST /api/v1/kafka/test-outbox-event",
        },
    )

    outbox_event = add_event_to_outbox(
        db,
        topic=AUDIT_EVENTS_TOPIC,
        event=event,
        key=aggregate_id,
    )

    db.commit()
    db.refresh(outbox_event)

    return {
        "service": "outbox",
        "status": "pending",
        "outbox_event": {
            "id": str(outbox_event.id),
            "topic": outbox_event.topic,
            "event_key": outbox_event.event_key,
            "event_type": outbox_event.event_type,
            "aggregate_type": outbox_event.aggregate_type,
            "aggregate_id": outbox_event.aggregate_id,
            "status": outbox_event.status,
            "retry_count": outbox_event.retry_count,
            "created_at": outbox_event.created_at,
            "published_at": outbox_event.published_at,
        },
        "event": event.to_kafka_dict(),
    }