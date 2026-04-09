from fastapi import APIRouter

from app.api.v1.endpoints import auth, catalog, categories, health, items, moderation, notifications, users

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health-check", tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(categories.router, prefix="/categories", tags=["categories"])
api_router.include_router(items.router, prefix="/items", tags=["items"])
api_router.include_router(catalog.router, prefix="/catalog", tags=["catalog"])
api_router.include_router(moderation.router, prefix="/admin/moderation", tags=["moderation"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])