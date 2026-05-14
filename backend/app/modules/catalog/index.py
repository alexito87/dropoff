from fastapi import APIRouter

from app.modules.catalog.routes.catalog_routes import router as catalog_routes
from app.modules.catalog.routes.category_routes import router as category_routes

router = APIRouter()

router.include_router(
    category_routes,
    prefix="/categories",
    tags=["categories"],
)

router.include_router(
    catalog_routes,
    prefix="/catalog",
    tags=["catalog"],
)