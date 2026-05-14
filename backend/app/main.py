from fastapi import FastAPI

from app.infrastructure.kafka.index import router as kafka_router
from app.modules.auth.index import router as auth_router
from app.modules.catalog.index import router as catalog_router
from app.modules.items.index import router as items_router
from app.modules.notifications.index import router as notifications_router
from app.modules.orders.index import router as orders_router
from app.modules.rentals.index import router as rentals_router
from app.modules.users.index import router as users_router


app = FastAPI(
    title="Dropoff Modular Monolith",
    description="Маркетплейс обмена вещами — модульный монолит",
    version="1.0.0",
)


@app.get("/")
async def root():
    return {"message": "Dropoff backend is running"}


@app.get("/api/v1/health-check", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(catalog_router, prefix="/api/v1")
app.include_router(items_router, prefix="/api/v1")
app.include_router(rentals_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")
app.include_router(orders_router, prefix="/api/v1")
app.include_router(kafka_router, prefix="/api/v1")

