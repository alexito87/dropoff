from fastapi import APIRouter

from app.modules.payments.routes.payments_routes import router as payments_routes

router = APIRouter()

router.include_router(
    payments_routes,
    prefix="/payments",
    tags=["payments"],
)