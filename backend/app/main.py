from fastapi import FastAPI

from app.infrastructure.registry import register_infrastructure
from app.modules.registry import register_modules


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


register_modules(app)
register_infrastructure(app)

