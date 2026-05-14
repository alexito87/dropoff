# index.py
# Точка подключения модуля к серверу

from fastapi import APIRouter

# Создаём роутер модуля
router = APIRouter()

# Импортируем эндпоинты (роуты) модуля
# from .routes import <route_files>
# Например:
# from .routes.user_routes import router as user_router
# router.include_router(user_router)

# Здесь можно подключать сервисы и контроллеры при необходимости

def include_module(app):
    """
    Подключение модуля к FastAPI приложению
    """
    app.include_router(router, prefix=f"/{router.tags[0] if router.tags else 'module'}")