"""Job queue service for managing generation jobs with ARQ.

This service provides the business logic for:
- Creating and enqueueing jobs
- Tracking job status and progress
- Managing retries with exponential backoff
- Cancelling jobs
- Publishing progress updates via Redis pub/sub
- Token deduction on job completion
"""

import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.arq_config import (
    DEFAULT_RETRY_CONFIG,
    RetryConfig,
    abort_job,
    enqueue_job,
    get_arq_pool,
)
from app.core.redis import get_redis
from app.models.generation_job import GenerationJob, JobStatus
from app.models.document import Document
from app.schemas.generation_job import (
    GenerationJobCreate,
    GenerationJobResponse,
    GenerationRequest,
    JobProgressUpdate,
    JobQueueInfo,
)

logger = logging.getLogger(__name__)

# Redis pub/sub channel for job progress updates
JOB_PROGRESS_CHANNEL = "overworld:job_progress"

# Redis key prefixes
JOB_PROGRESS_KEY_PREFIX = "overworld:job:{job_id}:progress"
JOB_CANCEL_KEY_PREFIX = "overworld:job:{job_id}:cancel"


class JobQueueService:
    """Service for managing generation jobs via ARQ queue."""

    def __init__(
        self,
        db: AsyncSession,
        retry_config: Optional[RetryConfig] = None,
    ):
        """Initialize the job queue service.

        Args:
            db: Database session for job persistence
            retry_config: Optional retry configuration (uses default if not provided)
        """
        self.db = db
        self.retry_config = retry_config or DEFAULT_RETRY_CONFIG

    async def create_job(
        self,
        user_id: int,
        job_data: GenerationJobCreate,
    ) -> GenerationJob:
        """Create a new generation job and enqueue it for processing.

        Args:
            user_id: ID of the user creating the job
            job_data: Job creation request data

        Returns:
            Created GenerationJob instance

        Raises:
            Exception: If job creation or enqueueing fails
        """
        # Generate unique ARQ job ID
        arq_job_id = f"gen-{uuid.uuid4().hex[:12]}"

        # Create job record in database
        job = GenerationJob(
            arq_job_id=arq_job_id,
            document_id=job_data.document_id,
            user_id=user_id,
            status=JobStatus.PENDING,
            progress_pct=0.0,
            progress_message="Job queued",
            retry_count=0,
            max_retries=job_data.max_retries,
            agent_state={
                "theme_id": job_data.theme_id,
                "options": job_data.options,
            },
        )

        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)

        # Create request payload for worker
        request = GenerationRequest(
            job_id=job.id,
            arq_job_id=arq_job_id,
            document_id=job_data.document_id,
            user_id=user_id,
            theme_id=job_data.theme_id,
            options=job_data.options,
            retry_count=0,
            max_retries=job_data.max_retries,
        )

        # Enqueue job to ARQ
        try:
            arq_job = await enqueue_job(
                "process_generation_job",
                request.model_dump(),
                _job_id=arq_job_id,
            )

            if arq_job is None:
                # Job already exists in queue (duplicate)
                logger.warning(f"Duplicate job ID {arq_job_id}, job already queued")

            logger.info(f"Created and enqueued job {job.id} with ARQ ID {arq_job_id}")

        except Exception as e:
            # Rollback job status if enqueueing fails
            job.status = JobStatus.FAILED
            job.error_msg = f"Failed to enqueue job: {str(e)}"
            job.error_code = "ENQUEUE_FAILED"
            await self.db.commit()
            logger.error(f"Failed to enqueue job {job.id}: {e}")
            raise

        return job

    async def get_job(self, job_id: int, user_id: int) -> Optional[GenerationJob]:
        """Get a job by ID for a specific user.

        Args:
            job_id: Job ID to fetch
            user_id: User ID (for authorization)

        Returns:
            GenerationJob if found and owned by user, None otherwise
        """
        stmt = select(GenerationJob).where(
            GenerationJob.id == job_id,
            GenerationJob.user_id == user_id,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_job_with_queue_info(
        self,
        job_id: int,
        user_id: int,
    ) -> Optional[tuple[GenerationJob, Optional[JobQueueInfo]]]:
        """Get a job with its queue position info.

        Args:
            job_id: Job ID to fetch
            user_id: User ID (for authorization)

        Returns:
            Tuple of (GenerationJob, JobQueueInfo) or None if not found
        """
        job = await self.get_job(job_id, user_id)
        if job is None:
            return None

        queue_info = None
        if job.status == JobStatus.PENDING:
            queue_info = await self._get_queue_position(job.id)

        return job, queue_info

    async def list_jobs(
        self,
        user_id: int,
        status_filter: Optional[JobStatus] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[GenerationJob], int]:
        """List jobs for a user with optional status filter.

        Args:
            user_id: User ID
            status_filter: Optional status to filter by
            limit: Maximum number of jobs to return
            offset: Offset for pagination

        Returns:
            Tuple of (jobs list, total count)
        """
        # Build base query
        base_stmt = select(GenerationJob).where(GenerationJob.user_id == user_id)

        if status_filter:
            base_stmt = base_stmt.where(GenerationJob.status == status_filter)

        # Get total count
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = await self.db.scalar(count_stmt) or 0

        # Get paginated results
        stmt = base_stmt.order_by(GenerationJob.created_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        jobs = list(result.scalars().all())

        return jobs, total

    async def cancel_job(self, job_id: int, user_id: int) -> Optional[GenerationJob]:
        """Cancel a job.

        Args:
            job_id: Job ID to cancel
            user_id: User ID (for authorization)

        Returns:
            Updated GenerationJob if cancelled, None if not found/already terminal
        """
        job = await self.get_job(job_id, user_id)
        if job is None:
            return None

        # Can only cancel pending or processing jobs
        if job.is_terminal:
            logger.warning(f"Cannot cancel job {job_id}: already in terminal state {job.status}")
            return None

        # Mark job as cancelled in database
        job.status = JobStatus.CANCELLED
        job.cancelled_at = datetime.now(timezone.utc)
        job.progress_message = "Job cancelled by user"

        # Set cancel flag in Redis for worker to detect
        redis = await get_redis()
        cancel_key = JOB_CANCEL_KEY_PREFIX.format(job_id=job_id)
        await redis.set(cancel_key, "1", ex=3600)  # Expire after 1 hour

        # Attempt to abort the ARQ job if it has an ARQ job ID
        if job.arq_job_id:
            try:
                await abort_job(job.arq_job_id)
                logger.info(f"Sent abort signal to ARQ job {job.arq_job_id}")
            except Exception as e:
                logger.warning(f"Failed to abort ARQ job {job.arq_job_id}: {e}")

        await self.db.commit()
        await self.db.refresh(job)

        # Publish cancellation event
        await self._publish_progress_update(job)

        logger.info(f"Cancelled job {job_id}")
        return job

    async def update_job_progress(
        self,
        job_id: int,
        progress_pct: float,
        progress_message: Optional[str] = None,
        agent_name: Optional[str] = None,
        agent_state: Optional[dict] = None,
    ) -> Optional[GenerationJob]:
        """Update job progress.

        Args:
            job_id: Job ID to update
            progress_pct: Progress percentage (0-100)
            progress_message: Optional human-readable progress message
            agent_name: Optional agent currently processing
            agent_state: Optional agent state to checkpoint

        Returns:
            Updated GenerationJob if found, None otherwise
        """
        stmt = select(GenerationJob).where(GenerationJob.id == job_id)
        result = await self.db.execute(stmt)
        job = result.scalar_one_or_none()

        if job is None:
            return None

        # Only update if job is still processing
        if job.status != JobStatus.PROCESSING:
            logger.warning(f"Cannot update progress for job {job_id}: status is {job.status}")
            return job

        job.progress_pct = progress_pct
        if progress_message:
            job.progress_message = progress_message

        if agent_state:
            # Merge agent state
            current_state = job.agent_state or {}
            if agent_name:
                current_state[agent_name] = agent_state
            else:
                current_state.update(agent_state)
            job.agent_state = current_state

        await self.db.commit()

        # Publish progress update
        await self._publish_progress_update(job, agent_name)

        return job

    async def mark_job_processing(self, job_id: int) -> Optional[GenerationJob]:
        """Mark a job as processing (called when worker picks up job).

        Args:
            job_id: Job ID to mark as processing

        Returns:
            Updated GenerationJob if found, None otherwise
        """
        stmt = select(GenerationJob).where(GenerationJob.id == job_id)
        result = await self.db.execute(stmt)
        job = result.scalar_one_or_none()

        if job is None:
            return None

        job.status = JobStatus.PROCESSING
        job.started_at = datetime.now(timezone.utc)
        job.progress_message = "Processing started"

        await self.db.commit()
        await self._publish_progress_update(job)

        return job

    async def mark_job_completed(
        self,
        job_id: int,
        map_id: Optional[int] = None,
        final_state: Optional[dict] = None,
    ) -> Optional[GenerationJob]:
        """Mark a job as completed and deduct tokens.

        Args:
            job_id: Job ID to mark as completed
            map_id: Optional generated map ID
            final_state: Optional final agent state

        Returns:
            Updated GenerationJob if found, None otherwise
        """
        stmt = select(GenerationJob).where(GenerationJob.id == job_id)
        result = await self.db.execute(stmt)
        job = result.scalar_one_or_none()

        if job is None:
            return None

        job.status = JobStatus.COMPLETED
        job.progress_pct = 100.0
        job.progress_message = "Generation completed"
        job.completed_at = datetime.now(timezone.utc)

        if map_id:
            job.map_id = map_id
        if final_state:
            job.agent_state = final_state

        await self.db.commit()

        # Deduct tokens for the completed job
        await self._deduct_tokens_for_job(job)

        await self._publish_progress_update(job)

        # Cleanup cancel key if exists
        await self._cleanup_job_keys(job_id)

        return job

    async def _deduct_tokens_for_job(self, job: GenerationJob) -> None:
        """Deduct tokens for a completed job.

        Args:
            job: The completed GenerationJob
        """
        try:
            from app.services.token_service import get_token_service

            token_service = get_token_service(self.db)

            # Calculate cost based on document size
            cost_estimate = await token_service.estimate_job_cost(
                document_id=str(job.document_id) if job.document_id else None
            )
            token_cost = cost_estimate["estimated_cost"]

            # Deduct tokens
            await token_service.deduct_tokens(
                user_id=job.user_id,
                amount=token_cost,
                reason=f"Map generation job #{job.id}",
                metadata={
                    "job_id": job.id,
                    "document_id": str(job.document_id) if job.document_id else None,
                    "map_id": job.map_id,
                },
            )

            logger.info(
                f"Deducted {token_cost} tokens from user {job.user_id} "
                f"for job {job.id}"
            )

        except Exception as e:
            # Log error but don't fail the job completion
            logger.error(
                f"Failed to deduct tokens for job {job.id}: {e}. "
                "Job marked as completed but tokens not deducted."
            )

    async def mark_job_failed(
        self,
        job_id: int,
        error_msg: str,
        error_code: Optional[str] = None,
        should_retry: bool = True,
    ) -> Optional[GenerationJob]:
        """Mark a job as failed, potentially scheduling a retry.

        Args:
            job_id: Job ID to mark as failed
            error_msg: Error message
            error_code: Optional error classification
            should_retry: Whether to attempt retry if retries remain

        Returns:
            Updated GenerationJob if found, None otherwise
        """
        stmt = select(GenerationJob).where(GenerationJob.id == job_id)
        result = await self.db.execute(stmt)
        job = result.scalar_one_or_none()

        if job is None:
            return None

        job.error_msg = error_msg
        job.error_code = error_code

        # Check if we should retry
        can_retry = should_retry and job.retry_count < job.max_retries
        is_retryable_error = self._is_retryable_error(error_code, error_msg)

        if can_retry and is_retryable_error:
            # Schedule retry with exponential backoff
            job.retry_count += 1
            delay_seconds = self.retry_config.get_delay(job.retry_count - 1)
            job.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
            job.status = JobStatus.PENDING
            job.progress_message = f"Retry {job.retry_count}/{job.max_retries} scheduled"

            await self.db.commit()

            # Re-enqueue job with delay
            request = GenerationRequest(
                job_id=job.id,
                arq_job_id=f"{job.arq_job_id}-r{job.retry_count}",
                document_id=str(job.document_id) if job.document_id else None,
                user_id=job.user_id,
                theme_id=job.agent_state.get("theme_id", "smb3"),
                options=job.agent_state.get("options", {}),
                retry_count=job.retry_count,
                max_retries=job.max_retries,
            )

            try:
                await enqueue_job(
                    "process_generation_job",
                    request.model_dump(),
                    _job_id=request.arq_job_id,
                    _defer_by=timedelta(seconds=delay_seconds),
                )
                logger.info(
                    f"Scheduled retry {job.retry_count} for job {job_id} "
                    f"in {delay_seconds} seconds"
                )
            except Exception as e:
                logger.error(f"Failed to schedule retry for job {job_id}: {e}")
                # Mark as failed if retry scheduling fails
                job.status = JobStatus.FAILED
                job.progress_message = f"Failed to schedule retry: {str(e)}"
                await self.db.commit()
        else:
            # No more retries, mark as permanently failed
            job.status = JobStatus.FAILED
            job.completed_at = datetime.now(timezone.utc)
            job.progress_message = "Job failed permanently"
            await self.db.commit()

            # Cleanup
            await self._cleanup_job_keys(job_id)

        await self._publish_progress_update(job)

        return job

    async def check_job_cancelled(self, job_id: int) -> bool:
        """Check if a job has been cancelled.

        This is called by workers to check if they should abort processing.

        Args:
            job_id: Job ID to check

        Returns:
            True if job is cancelled, False otherwise
        """
        redis = await get_redis()
        cancel_key = JOB_CANCEL_KEY_PREFIX.format(job_id=job_id)
        return await redis.exists(cancel_key) > 0

    async def _get_queue_position(self, job_id: int) -> JobQueueInfo:
        """Get queue position for a pending job.

        Args:
            job_id: Job ID to get position for

        Returns:
            JobQueueInfo with position and estimated wait
        """
        # Count jobs created before this one that are still pending
        stmt = select(func.count()).select_from(GenerationJob).where(
            GenerationJob.status == JobStatus.PENDING,
            GenerationJob.id < job_id,
        )
        jobs_ahead = await self.db.scalar(stmt) or 0

        # Estimate wait time (30 seconds per job average)
        estimated_wait_seconds = jobs_ahead * 30

        return JobQueueInfo(
            queue_position=jobs_ahead + 1,
            estimated_wait_seconds=estimated_wait_seconds,
            jobs_ahead=jobs_ahead,
        )

    async def _publish_progress_update(
        self,
        job: GenerationJob,
        agent_name: Optional[str] = None,
    ) -> None:
        """Publish progress update to Redis pub/sub.

        Args:
            job: Job to publish update for
            agent_name: Optional agent currently processing
        """
        try:
            redis = await get_redis()

            update = JobProgressUpdate(
                job_id=job.id,
                progress_pct=job.progress_pct,
                progress_message=job.progress_message,
                status=job.status,
                agent_name=agent_name,
            )

            # Publish to channel
            await redis.publish(JOB_PROGRESS_CHANNEL, update.model_dump_json())

            # Also store latest progress in a key for polling
            progress_key = JOB_PROGRESS_KEY_PREFIX.format(job_id=job.id)
            await redis.set(progress_key, update.model_dump_json(), ex=3600)

        except Exception as e:
            logger.warning(f"Failed to publish progress update for job {job.id}: {e}")

    async def _cleanup_job_keys(self, job_id: int) -> None:
        """Cleanup Redis keys for a completed/failed job.

        Args:
            job_id: Job ID to cleanup
        """
        try:
            redis = await get_redis()
            cancel_key = JOB_CANCEL_KEY_PREFIX.format(job_id=job_id)
            progress_key = JOB_PROGRESS_KEY_PREFIX.format(job_id=job_id)
            await redis.delete(cancel_key, progress_key)
        except Exception as e:
            logger.warning(f"Failed to cleanup keys for job {job_id}: {e}")

    def _is_retryable_error(
        self,
        error_code: Optional[str],
        error_msg: str,
    ) -> bool:
        """Determine if an error is retryable.

        Args:
            error_code: Optional error classification
            error_msg: Error message

        Returns:
            True if error is transient and worth retrying
        """
        # Non-retryable error codes
        non_retryable_codes = {
            "INVALID_INPUT",
            "AUTH_FAILED",
            "NOT_FOUND",
            "VALIDATION_ERROR",
            "PERMISSION_DENIED",
        }

        if error_code and error_code.upper() in non_retryable_codes:
            return False

        # Keywords indicating transient errors
        transient_keywords = [
            "timeout",
            "connection",
            "network",
            "rate limit",
            "temporary",
            "unavailable",
            "overload",
            "retry",
            "503",
            "504",
            "429",
        ]

        error_lower = error_msg.lower()
        return any(keyword in error_lower for keyword in transient_keywords)


async def get_job_queue_service(db: AsyncSession) -> JobQueueService:
    """Factory function to create JobQueueService.

    Args:
        db: Database session

    Returns:
        Configured JobQueueService instance
    """
    return JobQueueService(db)
