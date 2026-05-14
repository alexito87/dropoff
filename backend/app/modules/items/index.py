from fastapi import APIRouter

from app.modules.items.routes.items_routes import router as items_routes

router = APIRouter()

router.include_router(
    items_routes,
    prefix="/items",
    tags=["items"],
)