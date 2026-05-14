from fastapi import APIRouter

from app.infrastructure.kafka.routes.kafka_routes import router as kafka_routes

router = APIRouter()

router.include_router(
    kafka_routes,
    prefix="/kafka",
    tags=["kafka"],
)