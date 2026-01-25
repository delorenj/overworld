"""ARQ worker tasks for processing generation jobs.

This module defines the async task functions that are executed by ARQ workers.
Tasks include:
- process_generation_job: Main job processing task
- update_job_progress: Progress update task (can be called from other tasks)
- cleanup_stale_jobs: Maintenance task to clean up stuck jobs

Usage:
    Start worker with: arq app.workers.arq_tasks.WorkerSettings
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from arq import cron
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session_factory
from app.core.redis import redis_conn
from app.models.generation_job import GenerationJob, JobStatus
from app.schemas.generation_job import GenerationRequest
from app.services.job_queue import (
    JOB_CANCEL_KEY_PREFIX,
    JOB_PROGRESS_CHANNEL,
    JobQueueService,
)

logger = logging.getLogger(__name__)

# Progress checkpoints for the generation pipeline
PROGRESS_CHECKPOINTS = {
    "initialized": 5,
    "parser_started": 10,
    "parser_completed": 25,
    "artist_started": 30,
    "artist_completed": 50,
    "road_started": 55,
    "road_completed": 75,
    "icon_started": 80,
    "icon_completed": 95,
    "finalizing": 98,
    "completed": 100,
}


async def process_generation_job(ctx: dict, request_data: dict) -> dict:
    """Process a map generation job.

    This is the main task function that orchestrates the multi-agent
    map generation pipeline.

    Args:
        ctx: ARQ context containing redis connection and other metadata
        request_data: GenerationRequest data as dict

    Returns:
        Dict with job result information

    Note:
        This is a placeholder implementation. The actual pipeline integration
        will be done in STORY-004 (Multi-Agent Pipeline Foundation).
    """
    request = GenerationRequest(**request_data)
    job_id = request.job_id

    logger.info(f"Starting job {job_id} (ARQ: {request.arq_job_id})")

    # Get database session
    session_factory = get_session_factory()

    async with session_factory() as db:
        job_service = JobQueueService(db)

        # Check if job was cancelled before we started
        if await job_service.check_job_cancelled(job_id):
            logger.info(f"Job {job_id} was cancelled before processing started")
            return {"status": "cancelled", "job_id": job_id}

        # Mark job as processing
        await job_service.mark_job_processing(job_id)

        try:
            # === PLACEHOLDER PROCESSING PIPELINE ===
            # This will be replaced with actual multi-agent pipeline in STORY-004
            #
            # The pipeline will call these agents in sequence:
            # 1. Parser Agent - Extract structure from document
            # 2. Artist Agent - Generate visual elements
            # 3. Road Agent - Create pathways and connections
            # 4. Icon Agent - Place icons and markers

            # Simulate pipeline stages with progress updates
            stages = [
                ("parser_started", "Starting document parsing...", 2),
                ("parser_completed", "Document structure extracted", 3),
                ("artist_started", "Generating visual elements...", 2),
                ("artist_completed", "Visual elements created", 3),
                ("road_started", "Creating pathways...", 2),
                ("road_completed", "Pathways generated", 3),
                ("icon_started", "Placing icons...", 2),
                ("icon_completed", "Icons placed", 3),
                ("finalizing", "Finalizing map...", 1),
            ]

            for stage_name, message, delay in stages:
                # Check for cancellation between stages
                if await job_service.check_job_cancelled(job_id):
                    logger.info(f"Job {job_id} cancelled during {stage_name}")
                    return {"status": "cancelled", "job_id": job_id}

                # Update progress
                progress = PROGRESS_CHECKPOINTS.get(stage_name, 50)
                agent_name = stage_name.split("_")[0] if "_" in stage_name else None

                await job_service.update_job_progress(
                    job_id=job_id,
                    progress_pct=progress,
                    progress_message=message,
                    agent_name=agent_name,
                    agent_state={
                        "stage": stage_name,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )

                # Simulate work (will be replaced with actual agent calls)
                await asyncio.sleep(delay)

            # === END PLACEHOLDER ===

            # Mark job as completed
            # Note: map_id will be provided by actual pipeline when map is saved
            await job_service.mark_job_completed(
                job_id=job_id,
                map_id=None,  # Will be set by actual pipeline
                final_state={
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "pipeline_version": "0.1.0-placeholder",
                },
            )

            logger.info(f"Job {job_id} completed successfully")
            return {
                "status": "completed",
                "job_id": job_id,
                "message": "Map generation completed",
            }

        except asyncio.CancelledError:
            # Job was aborted
            logger.info(f"Job {job_id} was aborted")
            await job_service.mark_job_failed(
                job_id=job_id,
                error_msg="Job was aborted",
                error_code="ABORTED",
                should_retry=False,
            )
            return {"status": "aborted", "job_id": job_id}

        except Exception as e:
            # Job failed with error
            error_msg = str(e)
            error_code = type(e).__name__

            logger.error(f"Job {job_id} failed: {error_msg}")

            await job_service.mark_job_failed(
                job_id=job_id,
                error_msg=error_msg,
                error_code=error_code,
                should_retry=True,  # Let the service decide based on error type
            )

            return {
                "status": "failed",
                "job_id": job_id,
                "error": error_msg,
            }


async def update_job_progress(
    ctx: dict,
    job_id: int,
    progress_pct: float,
    progress_message: Optional[str] = None,
    agent_name: Optional[str] = None,
) -> dict:
    """Update job progress (can be called as a separate task).

    This task can be enqueued to update progress from external processes
    or as part of a distributed pipeline.

    Args:
        ctx: ARQ context
        job_id: Job ID to update
        progress_pct: Progress percentage (0-100)
        progress_message: Optional progress message
        agent_name: Optional agent name

    Returns:
        Dict with update result
    """
    session_factory = get_session_factory()

    async with session_factory() as db:
        job_service = JobQueueService(db)
        job = await job_service.update_job_progress(
            job_id=job_id,
            progress_pct=progress_pct,
            progress_message=progress_message,
            agent_name=agent_name,
        )

        if job is None:
            return {"status": "not_found", "job_id": job_id}

        return {
            "status": "updated",
            "job_id": job_id,
            "progress": progress_pct,
        }


async def cleanup_stale_jobs(ctx: dict) -> dict:
    """Clean up jobs stuck in PROCESSING state.

    This maintenance task finds jobs that have been processing for too long
    (likely due to worker crash) and marks them as failed for retry.

    Args:
        ctx: ARQ context

    Returns:
        Dict with cleanup results
    """
    # Jobs processing for more than 30 minutes are considered stale
    stale_threshold = datetime.now(timezone.utc) - timedelta(minutes=30)

    session_factory = get_session_factory()

    async with session_factory() as db:
        # Find stale jobs
        stmt = select(GenerationJob).where(
            GenerationJob.status == JobStatus.PROCESSING,
            GenerationJob.started_at < stale_threshold,
        )
        result = await db.execute(stmt)
        stale_jobs = result.scalars().all()

        cleaned_count = 0
        for job in stale_jobs:
            job_service = JobQueueService(db)
            await job_service.mark_job_failed(
                job_id=job.id,
                error_msg="Job timed out (worker may have crashed)",
                error_code="TIMEOUT",
                should_retry=True,
            )
            cleaned_count += 1
            logger.warning(f"Cleaned up stale job {job.id}")

        await db.commit()

        logger.info(f"Cleanup completed: {cleaned_count} stale jobs processed")
        return {
            "status": "completed",
            "cleaned_count": cleaned_count,
        }


# Worker settings for ARQ
class WorkerSettings:
    """ARQ Worker configuration.

    Usage: arq app.workers.arq_tasks.WorkerSettings
    """

    from app.core.arq_config import get_redis_settings

    redis_settings = get_redis_settings()
    queue_name = "overworld:jobs"

    # Worker behavior
    max_jobs = 10
    job_timeout = 600  # 10 minutes
    max_tries = 1  # We handle retries manually
    poll_delay = 0.5

    # Health check
    health_check_interval = 30

    # Registered task functions
    functions = [
        process_generation_job,
        update_job_progress,
        cleanup_stale_jobs,
    ]

    # Cron jobs for maintenance (run cleanup every 15 minutes)
    cron_jobs = [
        cron(cleanup_stale_jobs, minute={0, 15, 30, 45}),
    ]

    # Startup hook
    @staticmethod
    async def on_startup(ctx: dict) -> None:
        """Called when worker starts."""
        logger.info("ARQ Worker starting up...")
        # Initialize Redis connection for the worker
        await redis_conn.connect()
        logger.info("ARQ Worker ready to process jobs")

    # Shutdown hook
    @staticmethod
    async def on_shutdown(ctx: dict) -> None:
        """Called when worker shuts down."""
        logger.info("ARQ Worker shutting down...")
        await redis_conn.close()
        logger.info("ARQ Worker shutdown complete")
