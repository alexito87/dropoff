# index.py
# Точка подключения модуля к серверу

from fastapi import APIRouter

# Создаём роутер модуля
router = APIRouter()

from fastapi import APIRouter

from app.modules.auth.routes.auth_routes import router as auth_routes

router = APIRouter()
router.include_router(auth_routes, prefix="/auth", tags=["auth"])