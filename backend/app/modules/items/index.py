from fastapi import APIRouter

from app.modules.items.routes.items_routes import router as items_routes
from app.modules.items.routes.moderation_routes import router as moderation_routes

router = APIRouter()

router.include_router(
    items_routes,
    prefix="/items",
    tags=["items"],
)

router.include_router(
    moderation_routes,
    prefix="/moderation",
    tags=["moderation"],
)