from fastapi import APIRouter

from app.modules.catalog.routes.catalog_routes import router as catalog_routes
from app.modules.catalog.routes.categories_admin_routes import router as categories_admin_routes

router = APIRouter()

router.include_router(
    catalog_routes,
    prefix="/catalog",
    tags=["catalog"],
)

router.include_router(
    categories_admin_routes,
    prefix="/catalog",
    tags=["catalog-admin"],
)