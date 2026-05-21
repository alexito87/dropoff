from fastapi import APIRouter

from app.modules.admin.routes.admin_actions_routes import router as admin_actions_routes
from app.modules.admin.routes.admin_deliveries_routes import router as admin_deliveries_routes
from app.modules.admin.routes.admin_moderation_routes import router as admin_moderation_routes
from app.modules.admin.routes.admin_orders_routes import router as admin_orders_routes
from app.modules.admin.routes.admin_payments_routes import router as admin_payments_routes
from app.modules.admin.routes.admin_rentals_routes import router as admin_rentals_routes
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

router.include_router(
    admin_orders_routes,
    prefix="/admin/orders",
    tags=["admin-orders"],
)

router.include_router(
    admin_payments_routes,
    prefix="/admin/payments",
    tags=["admin-payments"],
)

router.include_router(
    admin_deliveries_routes,
    prefix="/admin/deliveries",
    tags=["admin-deliveries"],
)

router.include_router(
    admin_rentals_routes,
    prefix="/admin/rentals",
    tags=["admin-rentals"],
)