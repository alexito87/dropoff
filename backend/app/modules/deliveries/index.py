from fastapi import APIRouter

from app.modules.deliveries.routes.deliveries_routes import router as deliveries_routes

router = APIRouter()

router.include_router(
    deliveries_routes,
    prefix="/deliveries",
    tags=["deliveries"],
)