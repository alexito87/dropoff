from fastapi import APIRouter

from app.modules.orders.routes.cart_routes import router as cart_routes
from app.modules.orders.routes.orders_routes import router as orders_routes

router = APIRouter()

router.include_router(
    cart_routes,
    prefix="/cart",
    tags=["cart"],
)

router.include_router(
    orders_routes,
    prefix="/orders",
    tags=["orders"],
)