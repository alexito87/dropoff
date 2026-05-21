from fastapi import APIRouter

from app.modules.events.routes.events_routes import router as events_routes

router = APIRouter()

router.include_router(
    events_routes,
    prefix="/events",
    tags=["events"],
)