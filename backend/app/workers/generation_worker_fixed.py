"""Patched worker with sync/async fix."""

import asyncio
import logging

from app.workers import generation_worker

logger = logging.getLogger(__name__)


def sync_handle_message_wrapper(channel, method, properties, body):
    """Synchronous wrapper for async message handler.
    
    This creates a new event loop to run the async handler since
    pika's basic_consume expects a synchronous callback.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(
            generation_worker.worker._handle_message(channel, method, properties, body)
        )
    finally:
        loop.close()


# Monkey patch the worker
original_start = generation_worker.GenerationWorker.start


async def patched_start(self):
    """Patched start method that uses sync wrapper."""
    await generation_worker.rabbitmq.setup_topology()
    logger.info("Generation worker started (patched)")
    
    while self.processing:
        try:
            await generation_worker.rabbitmq.connect()
            channel = generation_worker.rabbitmq.channel
            
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(
                queue=generation_worker.QueueConfig.QUEUE_PENDING,
                on_message_callback=sync_handle_message_wrapper,  # Use sync wrapper
                auto_ack=False,
            )
            
            logger.info("Waiting for messages...")
            channel.start_consuming()
            
        except Exception as e:
            logger.error(f"Worker error: {e}")
            await asyncio.sleep(5)
            continue


generation_worker.GenerationWorker.start = patched_start
logger.info("Worker patched with sync/async fix")
