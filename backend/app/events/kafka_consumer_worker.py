import asyncio
import contextlib
import logging
import signal

from app.events.consumer_registry import KAFKA_CONSUMERS
from app.events.kafka_consumer_runner import run_kafka_consumer_loop

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _stop_task(task: asyncio.Task) -> None:
    if not task.done():
        task.cancel()

    with contextlib.suppress(asyncio.CancelledError):
        await task


async def main() -> None:
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop_event.set)

    logger.info("Kafka consumer worker starting")

    tasks = [
        asyncio.create_task(
            run_kafka_consumer_loop(
                consumer_config=consumer_config,
                stop_event=stop_event,
                startup_delay_seconds=10 + index * 2,
            )
        )
        for index, consumer_config in enumerate(KAFKA_CONSUMERS)
    ]

    try:
        await stop_event.wait()
    finally:
        logger.info("Kafka consumer worker stopping")

        for task in tasks:
            await _stop_task(task)

        logger.info("Kafka consumer worker stopped")


if __name__ == "__main__":
    asyncio.run(main())