#!/usr/bin/env python3
"""
Entrypoint for the Overworld generation worker service.

This script starts the background worker that processes map generation
jobs from the RabbitMQ queue.
"""

import asyncio
import logging
import signal
import sys

from app.workers.generation_worker import start_worker, stop_worker


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


def handle_shutdown(sig, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {sig}, shutting down worker...")
    asyncio.create_task(stop_worker())
    sys.exit(0)


async def main():
    """Main entry point for worker service."""
    logger.info("Starting Overworld generation worker...")
    
    # Register signal handlers
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    try:
        await start_worker()
    except KeyboardInterrupt:
        logger.info("Worker interrupted, shutting down...")
        await stop_worker()
    except Exception as e:
        logger.error(f"Worker failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
