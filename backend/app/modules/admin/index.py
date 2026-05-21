from fastapi import APIRouter

from app.modules.admin.routes.admin_actions_routes import router as admin_actions_routes
from app.modules.admin.routes.admin_moderation_routes import router as admin_moderation_routes
from app.modules.admin.routes.admin_routes import router as admin_routes

router = APIRouter()

router.include_router(
    admin_routes,
    prefix="/admin",
    tags=["admin"],
)

router.include_router(
    admin_actions_routes,
    prefix="/admin/actions",
    tags=["admin-actions"],
)

router.include_router(
    admin_moderation_routes,
    prefix="/admin",
    tags=["admin-moderation"],
)