from fastapi import FastAPI

from app.modules.auth.index import router as auth_router
from app.modules.catalog.index import router as catalog_router
from app.modules.items.index import router as items_router
from app.modules.notifications.index import router as notifications_router
from app.modules.orders.index import router as orders_router
from app.modules.rentals.index import router as rentals_router
from app.modules.users.index import router as users_router
from app.modules.deliveries.index import router as deliveries_router


API_V1_PREFIX = "/api/v1"


def register_modules(app: FastAPI) -> None:
    app.include_router(auth_router, prefix=API_V1_PREFIX)
    app.include_router(users_router, prefix=API_V1_PREFIX)
    app.include_router(catalog_router, prefix=API_V1_PREFIX)
    app.include_router(items_router, prefix=API_V1_PREFIX)
    app.include_router(rentals_router, prefix=API_V1_PREFIX)
    app.include_router(notifications_router, prefix=API_V1_PREFIX)
    app.include_router(orders_router, prefix=API_V1_PREFIX)
    app.include_router(deliveries_router, prefix=API_V1_PREFIX)