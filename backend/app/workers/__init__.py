"""Worker startup script for generation jobs."""

import asyncio
import logging
import signal
import sys

from app.workers.generation_worker import start_worker, stop_worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


async def main() -> None:
    """Main worker process."""
    logger.info("Starting generation worker process")

    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        asyncio.create_task(stop_worker())

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        await start_worker()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Worker failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
