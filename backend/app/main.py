import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.events.outbox_publisher import run_outbox_publisher_loop
from app.events.producer import kafka_event_producer
from app.infrastructure.registry import register_infrastructure
from app.modules.registry import register_modules


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop_outbox_publisher = asyncio.Event()
    outbox_publisher_task: asyncio.Task | None = None

    if settings.OUTBOX_PUBLISHER_ENABLED:
        outbox_publisher_task = asyncio.create_task(
            run_outbox_publisher_loop(stop_outbox_publisher)
        )

    try:
        yield
    finally:
        stop_outbox_publisher.set()

        if outbox_publisher_task:
            await outbox_publisher_task

        await kafka_event_producer.stop()


app = FastAPI(
    title="Dropoff Modular Monolith",
    description="Маркетплейс обмена вещами — модульный монолит",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "Dropoff backend is running"}


@app.get("/api/v1/health-check", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


register_modules(app)
register_infrastructure(app)