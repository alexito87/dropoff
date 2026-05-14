from fastapi import APIRouter

from app.modules.rentals.routes.rentals_routes import router as rentals_routes

router = APIRouter()

router.include_router(
    rentals_routes,
    prefix="/rentals",
    tags=["rentals"],
)