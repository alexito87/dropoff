import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.api import api_router
from app.core.config import settings
from app.events.producer import kafka_event_producer
from app.services.cache import cache_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.project_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.on_event("startup")
async def on_startup() -> None:
    if not settings.REDIS_ENABLED:
        logger.info("Redis cache is disabled by configuration")
    elif cache_service.ping():
        logger.info("Redis cache is connected")
    else:
        logger.warning("Redis cache is unavailable; backend will continue without cache")

    if not settings.KAFKA_ENABLED:
        logger.info("Kafka producer is disabled by configuration")
        return

    try:
        await kafka_event_producer.start()
        logger.info("Kafka producer is connected")
    except Exception:
        logger.exception("Kafka producer is unavailable; backend will continue without producer")


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await kafka_event_producer.stop()
    logger.info("Kafka producer is stopped")


@app.get("/")
def root():
    return {"message": "dropoff backend is running"}