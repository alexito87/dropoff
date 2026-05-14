from fastapi import APIRouter

from app.modules.users.routes.users_routes import router as users_routes

router = APIRouter()
router.include_router(users_routes, prefix="/users", tags=["users"])