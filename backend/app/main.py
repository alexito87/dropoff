from fastapi import FastAPI

from app.api.v1.api import api_router as legacy_api_router
from app.modules.auth.index import router as auth_router
from app.modules.users.index import router as users_router


app = FastAPI(
    title="Dropoff Modular Monolith",
    description="Маркетплейс обмена вещами — модульный монолит",
    version="1.0.0",
)


@app.get("/")
async def root():
    return {"message": "Dropoff backend is running"}


app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(legacy_api_router, prefix="/api/v1")

