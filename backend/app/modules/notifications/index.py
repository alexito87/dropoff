from fastapi import APIRouter

from app.modules.notifications.routes.notifications_routes import router as notifications_routes

router = APIRouter()

router.include_router(
    notifications_routes,
    prefix="/notifications",
    tags=["notifications"],
)