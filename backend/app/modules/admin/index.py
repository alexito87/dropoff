from fastapi import APIRouter

from app.modules.admin.routes.admin_routes import router as admin_routes

router = APIRouter()

router.include_router(
    admin_routes,
    prefix="/admin",
    tags=["admin"],
)