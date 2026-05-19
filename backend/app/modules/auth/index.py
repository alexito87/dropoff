from fastapi import APIRouter

from app.modules.auth.routes.auth_routes import router as auth_routes


router = APIRouter()
router.include_router(auth_routes, prefix="/auth", tags=["auth"])