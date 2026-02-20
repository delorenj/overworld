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
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.core.pubsub import pubsub_manager
from app.core.queue import QueueConfig, rabbitmq
from app.models.document import Document
from app.models.generation_job import GenerationJob, JobStatus
from app.models.map import Map
from app.models.theme import Theme
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
        self._main_loop: Optional[asyncio.AbstractEventLoop] = None

    def _sync_handle_message(self, channel, method, properties, body) -> None:
        """Synchronous pika callback that dispatches to the main event loop.

        Pika's basic_consume runs callbacks on the consumer thread.
        asyncpg connections are bound to the event loop that created them,
        so we MUST dispatch async work back to the main loop rather than
        creating throwaway loops (which causes InterfaceError).
        """
        future = asyncio.run_coroutine_threadsafe(
            self._handle_message(channel, method, properties, body),
            self._main_loop,
        )
        # Block the consumer thread until the async handler completes.
        # This honours prefetch_count=1 back-pressure.
        future.result()

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

        self._main_loop = asyncio.get_running_loop()

        # Force-initialise the async engine on *this* loop so every
        # subsequent get_async_session() reuses it correctly.
        from app.core.database import get_engine
        get_engine()

        while self.processing:
            try:
                await rabbitmq.connect()

                # Run blocking consumer in thread executor to avoid blocking event loop
                await self._main_loop.run_in_executor(None, self._run_consumer)

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

                # Persist a generated map artifact so e2e flow has tangible output
                map_id = await self._create_map_artifact(db, request)

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
                    map_id=map_id,
                )

                # Broadcast completion event
                await pubsub_manager.publish_job_completed(
                    job_id=request.job_id,
                    completed_at=end_time,
                    map_id=map_id,
                    total_duration_seconds=duration,
                )

                logger.info(
                    f"Job {request.job_id}: Processing complete in {duration:.2f}s (map_id={map_id})"
                )

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

    async def _create_map_artifact(self, db: AsyncSession, request: GenerationRequest) -> int:
        """Create a persisted map record for completed jobs.

        This is a lightweight placeholder artifact until the full coordinator
        pipeline writes richer map payloads.
        """
        job_stmt = select(GenerationJob).where(GenerationJob.id == request.job_id)
        job_result = await db.execute(job_stmt)
        job = job_result.scalar_one()

        theme = await self._get_or_create_default_theme(db)

        document = None
        if request.document_id:
            try:
                document_uuid = UUID(str(request.document_id))
                doc_stmt = select(Document).where(Document.id == document_uuid)
                doc_result = await db.execute(doc_stmt)
                document = doc_result.scalar_one_or_none()
            except ValueError:
                logger.warning(
                    "Job %s has invalid document_id for artifact creation: %s",
                    request.job_id,
                    request.document_id,
                )

        hierarchy = self._build_placeholder_hierarchy(document)
        map_name = (
            f"Generated Map - {document.filename}" if document else f"Generated Map #{request.job_id}"
        )

        map_record = Map(
            user_id=request.user_id,
            theme_id=theme.id,
            name=map_name,
            hierarchy=hierarchy,
            watermarked=True,
            r2_url=f"generated://maps/job-{request.job_id}.json",
        )

        db.add(map_record)
        await db.flush()

        job.map_id = map_record.id
        await db.commit()

        logger.info("Created map artifact for job %s -> map_id=%s", request.job_id, map_record.id)
        return map_record.id

    async def _get_or_create_default_theme(self, db: AsyncSession) -> Theme:
        """Get the default SMB3 theme, creating it if missing."""
        stmt = select(Theme).where(Theme.name == "smb3")
        result = await db.execute(stmt)
        theme = result.scalar_one_or_none()

        if theme:
            return theme

        theme = Theme(
            name="smb3",
            description="Default SMB3-inspired theme",
            is_premium=False,
            asset_manifest={
                "palette": {
                    "ground": "#7c5a2a",
                    "grass": "#48a14d",
                    "water": "#3a7bd5",
                    "road": "#c8a96a",
                },
                "tileset": "smb3",
                "icons": "default",
            },
        )
        db.add(theme)
        await db.flush()
        logger.info("Created default theme 'smb3' (id=%s)", theme.id)
        return theme

    def _build_placeholder_hierarchy(self, document: Optional[Document]) -> dict:
        """Build fallback hierarchy payload for generated artifact."""
        if document and isinstance(document.processed_content, dict):
            return document.processed_content

        title = document.filename if document else "Generated Overworld"
        return {
            "L0": {
                "id": "root",
                "title": title,
                "description": "Auto-generated placeholder hierarchy",
            },
            "L1": [
                {
                    "id": "milestone-1",
                    "title": "Initial Milestone",
                    "content": "Worker-generated artifact",
                    "parent_id": "root",
                    "metadata": {"source": "generation_worker"},
                }
            ],
            "L2": [],
            "L3": [],
            "L4": [],
        }

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
        map_id: Optional[int] = None,
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
        if map_id is not None:
            job.map_id = map_id

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
