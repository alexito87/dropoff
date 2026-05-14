from fastapi import FastAPI

from app.infrastructure.kafka.index import router as kafka_router


API_V1_PREFIX = "/api/v1"


def register_infrastructure(app: FastAPI) -> None:
    app.include_router(kafka_router, prefix=API_V1_PREFIX)