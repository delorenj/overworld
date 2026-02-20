"""Background worker for processing generation jobs.

This module provides the GenerationWorker class that processes map generation
jobs from the RabbitMQ queue. It integrates with the Redis pub/sub system
to broadcast real-time progress updates to connected WebSocket clients.

Progress Events:
- job_started: Broadcast when job processing begins
- progress_update: Broadcast periodically during processing
- job_completed: Broadcast when job finishes successfully
- job_failed: Broadcast when job fails
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.core.pubsub import pubsub_manager
from app.core.queue import QueueConfig, rabbitmq
from app.models.generation_job import GenerationJob, JobStatus
from app.schemas.generation_job import GenerationRequest


logger = logging.getLogger(__name__)


class GenerationWorker:
    """Background worker for processing generation jobs.

    This worker:
    - Consumes jobs from RabbitMQ queue
    - Processes generation requests
    - Updates job status in database
    - Broadcasts progress events via Redis pub/sub
    """

    def __init__(self):
        """Initialize the generation worker."""
        self.processing = False
        self.current_job_id: Optional[int] = None

    def _sync_handle_message(self, channel, method, properties, body) -> None:
        """Synchronous wrapper for async message handler.
        
        Runs the async handler in a new event loop since pika callbacks
        are synchronous but our handler logic is async.
        """
        # Create isolated event loop for this message
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                self._handle_message(channel, method, properties, body)
            )
        finally:
            loop.close()
            asyncio.set_event_loop(None)

    def _run_consumer(self) -> None:
        """Run the blocking consumer loop (called in thread executor)."""
        try:
            channel = rabbitmq.channel
            channel.basic_qos(prefetch_count=1)
            channel.basic_consume(
                queue=QueueConfig.QUEUE_PENDING,
                on_message_callback=self._sync_handle_message,
                auto_ack=False,
            )
            
            logger.info("Waiting for messages...")
            channel.start_consuming()
            
        except Exception as e:
            logger.error(f"Consumer error: {e}")
            raise

    async def start(self) -> None:
        """Start the worker and begin consuming jobs."""
        await rabbitmq.setup_topology()
        logger.info("Generation worker started")

        loop = asyncio.get_event_loop()

        while self.processing:
            try:
                await rabbitmq.connect()
                
                # Run blocking consumer in thread executor to avoid blocking event loop
                await loop.run_in_executor(None, self._run_consumer)

            except Exception as e:
                logger.error(f"Worker error: {e}")
                await asyncio.sleep(5)
                continue

    async def stop(self) -> None:
        """Stop the worker gracefully."""
        self.processing = False
        await rabbitmq.close()
        logger.info("Generation worker stopped")

    async def _handle_message(self, channel, method, properties, body) -> None:
        """Handle incoming job message."""
        request = None
        try:
            message_data = json.loads(body.decode())
            request = GenerationRequest(**message_data)

            logger.info(f"Processing job {request.job_id}")
            self.current_job_id = request.job_id

            await asyncio.wait_for(
                self._process_job(request),
                timeout=120.0,
            )

            channel.basic_ack(delivery_tag=method.delivery_tag)
            logger.info(f"Completed job {request.job_id}")

        except asyncio.TimeoutError:
            logger.error(f"Job {request.job_id} timed out")
            await self._handle_timeout(request)
            channel.basic_ack(delivery_tag=method.delivery_tag)

        except Exception as e:
            if request:
                logger.error(f"Job {request.job_id} failed: {e}")
                await self._handle_failure(request, str(e))
            else:
                logger.error(f"Failed to parse message: {e}")
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    async def _process_job(self, request: GenerationRequest) -> None:
        """Process a single generation job.

        This method:
        1. Updates job status to PROCESSING
        2. Broadcasts job_started event
        3. Processes the job with progress updates
        4. Updates status to COMPLETED and broadcasts completion
        """
        async with get_async_session() as db:
            start_time = datetime.now(timezone.utc)

            try:
                # Update to PROCESSING and broadcast start
                await self._update_job_status(
                    db=db,
                    job_id=request.job_id,
                    status=JobStatus.PROCESSING,
                    progress=0.0,
                    progress_message="Starting generation...",
                )

                # Broadcast job started event
                await pubsub_manager.publish_job_started(
                    job_id=request.job_id,
                    started_at=start_time,
                    agent_name="parser",
                )

                # TODO: Integrate with CoordinatorAgent when pipeline is wired up
                # For now, simulate progress updates for testing
                await self._simulate_progress(db, request.job_id)

                # Calculate total duration
                end_time = datetime.now(timezone.utc)
                duration = (end_time - start_time).total_seconds()

                # Update to COMPLETED
                await self._update_job_status(
                    db=db,
                    job_id=request.job_id,
                    status=JobStatus.COMPLETED,
                    progress=100.0,
                    progress_message="Generation complete",
                )

                # Broadcast completion event
                await pubsub_manager.publish_job_completed(
                    job_id=request.job_id,
                    completed_at=end_time,
                    map_id=None,  # Will be set when actual map is created
                    total_duration_seconds=duration,
                )

                logger.info(f"Job {request.job_id}: Processing complete in {duration:.2f}s")

            except Exception as e:
                # Update to FAILED
                failed_at = datetime.now(timezone.utc)
                await self._update_job_status(
                    db=db,
                    job_id=request.job_id,
                    status=JobStatus.FAILED,
                    progress=0.0,
                    error_msg=str(e),
                )

                # Broadcast failure event
                await pubsub_manager.publish_job_failed(
                    job_id=request.job_id,
                    error_message=str(e),
                    failed_at=failed_at,
                    error_code="PROCESSING_ERROR",
                    can_retry=request.retry_count < request.max_retries,
                    retry_count=request.retry_count,
                    max_retries=request.max_retries,
                )
                raise

    async def _simulate_progress(self, db: AsyncSession, job_id: int) -> None:
        """Simulate progress updates for testing.

        This will be replaced with actual agent progress tracking
        when the CoordinatorAgent is integrated.
        """
        stages = [
            ("parser", "Parsing document structure...", 25.0),
            ("artist", "Generating visual layout...", 50.0),
            ("road", "Creating road network...", 75.0),
            ("icon", "Placing icons and labels...", 95.0),
        ]

        for agent_name, message, progress in stages:
            await asyncio.sleep(0.5)  # Simulate processing time

            # Update database
            await self._update_job_status(
                db=db,
                job_id=job_id,
                status=JobStatus.PROCESSING,
                progress=progress,
                progress_message=message,
            )

            # Broadcast progress update
            await pubsub_manager.publish_progress(
                job_id=job_id,
                progress_pct=progress,
                progress_message=message,
                agent_name=agent_name,
            )

    async def _update_job_status(
        self,
        db: AsyncSession,
        job_id: int,
        status: JobStatus,
        progress: float,
        progress_message: Optional[str] = None,
        error_msg: Optional[str] = None,
    ) -> None:
        """Update job status in database.

        Args:
            db: Database session
            job_id: Job ID to update
            status: New job status
            progress: Progress percentage (0-100)
            progress_message: Human-readable progress message
            error_msg: Error message (if failed)
        """
        stmt = select(GenerationJob).where(GenerationJob.id == job_id)
        result = await db.execute(stmt)
        job = result.scalar_one()

        job.status = status
        job.progress_pct = progress
        job.progress_message = progress_message
        job.error_msg = error_msg

        now = datetime.now(timezone.utc)

        if status == JobStatus.PROCESSING and not job.started_at:
            job.started_at = now
        elif status in [JobStatus.COMPLETED, JobStatus.FAILED] and not job.completed_at:
            job.completed_at = now

        await db.commit()

        logger.info(f"Job {job_id}: {status.value} ({progress}%) - {progress_message or ''}")

    async def _handle_timeout(self, request: GenerationRequest) -> None:
        """Handle job timeout."""
        failed_at = datetime.now(timezone.utc)

        async with get_async_session() as db:
            await self._update_job_status(
                db=db,
                job_id=request.job_id,
                status=JobStatus.FAILED,
                progress=0.0,
                progress_message="Job timed out",
                error_msg="Generation timeout exceeded",
            )

        # Broadcast failure event
        await pubsub_manager.publish_job_failed(
            job_id=request.job_id,
            error_message="Generation timeout exceeded",
            failed_at=failed_at,
            error_code="TIMEOUT",
            can_retry=request.retry_count < request.max_retries,
            retry_count=request.retry_count,
            max_retries=request.max_retries,
        )

        await rabbitmq.publish_message(
            routing_key=QueueConfig.ROUTING_KEY_FAILED,
            message=json.dumps(request.model_dump()).encode(),
        )

    async def _handle_failure(self, request: GenerationRequest, error: str) -> None:
        """Handle job failure."""
        failed_at = datetime.now(timezone.utc)

        async with get_async_session() as db:
            await self._update_job_status(
                db=db,
                job_id=request.job_id,
                status=JobStatus.FAILED,
                progress=0.0,
                progress_message="Job failed",
                error_msg=error,
            )

        # Broadcast failure event
        can_retry = self._is_transient_error(error) and request.retry_count < request.max_retries
        await pubsub_manager.publish_job_failed(
            job_id=request.job_id,
            error_message=error,
            failed_at=failed_at,
            error_code="TRANSIENT_ERROR" if self._is_transient_error(error) else "PERMANENT_ERROR",
            can_retry=can_retry,
            retry_count=request.retry_count,
            max_retries=request.max_retries,
        )

        if self._is_transient_error(error):
            await rabbitmq.publish_message(
                routing_key=QueueConfig.ROUTING_KEY_RETRY,
                message=json.dumps(request.model_dump()).encode(),
            )
        else:
            await rabbitmq.publish_message(
                routing_key=QueueConfig.ROUTING_KEY_FAILED,
                message=json.dumps(request.model_dump()).encode(),
            )

    def _is_transient_error(self, error: str) -> bool:
        """Determine if error is transient (retryable) or permanent."""
        transient_indicators = [
            "timeout",
            "connection",
            "network",
            "api rate limit",
            "temporary",
        ]

        error_lower = error.lower()
        return any(indicator in error_lower for indicator in transient_indicators)


worker = GenerationWorker()


async def start_worker() -> None:
    """Start generation worker."""
    worker.processing = True
    await worker.start()


async def stop_worker() -> None:
    """Stop generation worker."""
    await worker.stop()


# Utility function for broadcasting progress from other parts of the code
async def broadcast_progress(
    job_id: int,
    progress_pct: float,
    progress_message: Optional[str] = None,
    agent_name: Optional[str] = None,
    stage: Optional[str] = None,
) -> int:
    """Broadcast a progress update for a job.

    This is a convenience function that can be called from agents
    or other processing code to broadcast progress updates.

    Args:
        job_id: Job ID
        progress_pct: Progress percentage (0-100)
        progress_message: Human-readable progress message
        agent_name: Current agent name
        stage: Current processing stage

    Returns:
        Number of subscribers that received the message
    """
    return await pubsub_manager.publish_progress(
        job_id=job_id,
        progress_pct=progress_pct,
        progress_message=progress_message,
        agent_name=agent_name,
        stage=stage,
    )
