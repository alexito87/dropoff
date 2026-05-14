from fastapi import APIRouter

from app.modules.orders.routes.orders_routes import router as orders_routes

router = APIRouter()

router.include_router(
    orders_routes,
    prefix="/orders",
    tags=["orders"],
)