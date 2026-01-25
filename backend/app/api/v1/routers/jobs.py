"""API routes for job queue management.

This module provides REST endpoints for:
- Creating generation jobs (POST /api/v1/jobs)
- Getting job status (GET /api/v1/jobs/{id})
- Listing user jobs (GET /api/v1/jobs)
- Cancelling jobs (DELETE /api/v1/jobs/{id})
- Getting job progress (GET /api/v1/jobs/{id}/progress)

Jobs are processed via ARQ (Async Redis Queue) with:
- Progress tracking (0-100%)
- Retry logic with exponential backoff
- Job cancellation support
- Token balance checking and deduction
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_job_queue_service
from app.models.generation_job import JobStatus
from app.models.user import User
from app.schemas.generation_job import (
    GenerationJobCreate,
    GenerationJobResponse,
    JobCancellationResponse,
    JobListResponse,
    JobProgressUpdate,
)
from app.services.job_queue import JobQueueService
from app.services.token_service import get_token_service, InsufficientTokensError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=GenerationJobResponse,
    summary="Create generation job",
    description="Create a new map generation job and queue it for processing",
)
async def create_job(
    job_data: GenerationJobCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    job_service: JobQueueService = Depends(get_job_queue_service),
) -> GenerationJobResponse:
    """Create a new map generation job.

    The job will be queued for processing by an ARQ worker.
    Returns immediately with job status (PENDING).

    Token balance is checked before job creation. Tokens are deducted
    when the job completes successfully.

    Args:
        job_data: Job creation request
        current_user: Authenticated user
        db: Database session
        job_service: Job queue service

    Returns:
        GenerationJobResponse with job details and queue position

    Raises:
        HTTPException: 402 if insufficient token balance
        HTTPException: 500 if job creation fails
    """
    # Check token balance before creating job
    token_service = get_token_service(db)

    # Estimate cost based on document
    cost_estimate = await token_service.estimate_job_cost(
        document_id=job_data.document_id
    )
    estimated_cost = cost_estimate["estimated_cost"]

    # Check if user has sufficient balance
    try:
        has_balance = await token_service.check_sufficient_balance(
            current_user.id, estimated_cost
        )
        if not has_balance:
            current_balance = await token_service.get_balance(current_user.id)
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "message": "Insufficient token balance",
                    "required": estimated_cost,
                    "available": current_balance,
                    "shortfall": estimated_cost - current_balance,
                },
            )
    except InsufficientTokensError as e:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "message": "Insufficient token balance",
                "required": e.required,
                "available": e.available,
                "shortfall": e.required - e.available,
            },
        )

    try:
        job = await job_service.create_job(
            user_id=current_user.id,
            job_data=job_data,
        )

        # Get queue position for response
        result = await job_service.get_job_with_queue_info(job.id, current_user.id)
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve created job",
            )

        job, queue_info = result

        return GenerationJobResponse(
            id=job.id,
            arq_job_id=job.arq_job_id,
            status=job.status,
            progress_pct=job.progress_pct,
            progress_message=job.progress_message,
            queue_position=queue_info.queue_position if queue_info else None,
            estimated_wait_seconds=queue_info.estimated_wait_seconds if queue_info else None,
            document_id=str(job.document_id) if job.document_id else None,
            retry_count=job.retry_count,
            max_retries=job.max_retries,
            next_retry_at=job.next_retry_at,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            cancelled_at=job.cancelled_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create job: {str(e)}",
        )


@router.get(
    "/{job_id}",
    response_model=GenerationJobResponse,
    summary="Get job status",
    description="Get the current status and details of a generation job",
)
async def get_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    job_service: JobQueueService = Depends(get_job_queue_service),
) -> GenerationJobResponse:
    """Get status and details of a generation job.

    Args:
        job_id: Job ID to retrieve
        current_user: Authenticated user (must own the job)
        job_service: Job queue service

    Returns:
        GenerationJobResponse with current job status

    Raises:
        HTTPException: 404 if job not found or not owned by user
    """
    result = await job_service.get_job_with_queue_info(job_id, current_user.id)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    job, queue_info = result

    return GenerationJobResponse(
        id=job.id,
        arq_job_id=job.arq_job_id,
        status=job.status,
        progress_pct=job.progress_pct,
        progress_message=job.progress_message,
        queue_position=queue_info.queue_position if queue_info else None,
        estimated_wait_seconds=queue_info.estimated_wait_seconds if queue_info else None,
        map_id=job.map_id,
        document_id=str(job.document_id) if job.document_id else None,
        retry_count=job.retry_count,
        max_retries=job.max_retries,
        next_retry_at=job.next_retry_at,
        error_msg=job.error_msg,
        error_code=job.error_code,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        cancelled_at=job.cancelled_at,
    )


@router.get(
    "",
    response_model=JobListResponse,
    summary="List jobs",
    description="List generation jobs for the current user with optional status filter",
)
async def list_jobs(
    status_filter: Optional[JobStatus] = Query(
        default=None,
        description="Filter jobs by status",
    ),
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of jobs to return",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Offset for pagination",
    ),
    current_user: User = Depends(get_current_user),
    job_service: JobQueueService = Depends(get_job_queue_service),
) -> JobListResponse:
    """List generation jobs for the current user.

    Args:
        status_filter: Optional status to filter by
        limit: Maximum jobs to return (1-100)
        offset: Pagination offset
        current_user: Authenticated user
        job_service: Job queue service

    Returns:
        JobListResponse with paginated job list
    """
    jobs, total = await job_service.list_jobs(
        user_id=current_user.id,
        status_filter=status_filter,
        limit=limit,
        offset=offset,
    )

    job_responses = [
        GenerationJobResponse(
            id=job.id,
            arq_job_id=job.arq_job_id,
            status=job.status,
            progress_pct=job.progress_pct,
            progress_message=job.progress_message,
            map_id=job.map_id,
            document_id=str(job.document_id) if job.document_id else None,
            retry_count=job.retry_count,
            max_retries=job.max_retries,
            next_retry_at=job.next_retry_at,
            error_msg=job.error_msg,
            error_code=job.error_code,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            cancelled_at=job.cancelled_at,
        )
        for job in jobs
    ]

    return JobListResponse(
        jobs=job_responses,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.delete(
    "/{job_id}",
    response_model=JobCancellationResponse,
    summary="Cancel job",
    description="Cancel a pending or processing job",
)
async def cancel_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    job_service: JobQueueService = Depends(get_job_queue_service),
) -> JobCancellationResponse:
    """Cancel a generation job.

    Jobs can only be cancelled if they are in PENDING or PROCESSING state.
    Completed, failed, or already cancelled jobs cannot be cancelled.

    Args:
        job_id: Job ID to cancel
        current_user: Authenticated user (must own the job)
        job_service: Job queue service

    Returns:
        JobCancellationResponse with cancellation details

    Raises:
        HTTPException: 404 if job not found
        HTTPException: 409 if job is already in terminal state
    """
    # First check if job exists
    job = await job_service.get_job(job_id, current_user.id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    if job.is_terminal:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot cancel job in {job.status.value} state",
        )

    # Cancel the job
    cancelled_job = await job_service.cancel_job(job_id, current_user.id)

    if cancelled_job is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel job",
        )

    return JobCancellationResponse(
        id=cancelled_job.id,
        status=cancelled_job.status,
        cancelled_at=cancelled_job.cancelled_at,
        message="Job cancelled successfully",
    )


@router.get(
    "/{job_id}/progress",
    response_model=JobProgressUpdate,
    summary="Get job progress",
    description="Get real-time progress information for a job",
)
async def get_job_progress(
    job_id: int,
    current_user: User = Depends(get_current_user),
    job_service: JobQueueService = Depends(get_job_queue_service),
) -> JobProgressUpdate:
    """Get current progress for a job.

    This endpoint is optimized for polling progress updates.
    For real-time updates, consider using WebSocket or SSE.

    Args:
        job_id: Job ID to get progress for
        current_user: Authenticated user (must own the job)
        job_service: Job queue service

    Returns:
        JobProgressUpdate with current progress

    Raises:
        HTTPException: 404 if job not found
    """
    job = await job_service.get_job(job_id, current_user.id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    # Get current agent from state if available
    agent_name = None
    if job.agent_state:
        # Find the most recently updated agent
        for agent in ["icon", "road", "artist", "parser"]:
            if agent in job.agent_state:
                agent_name = agent
                break

    return JobProgressUpdate(
        job_id=job.id,
        progress_pct=job.progress_pct,
        progress_message=job.progress_message,
        status=job.status,
        agent_name=agent_name,
    )


@router.post(
    "/{job_id}/retry",
    response_model=GenerationJobResponse,
    summary="Retry failed job",
    description="Manually retry a failed job",
)
async def retry_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    job_service: JobQueueService = Depends(get_job_queue_service),
) -> GenerationJobResponse:
    """Manually retry a failed job.

    This allows retrying a job that has exhausted its automatic retries
    or was marked as non-retryable.

    Args:
        job_id: Job ID to retry
        current_user: Authenticated user (must own the job)
        db: Database session
        job_service: Job queue service

    Returns:
        GenerationJobResponse with new job status

    Raises:
        HTTPException: 404 if job not found
        HTTPException: 409 if job is not in FAILED state
    """
    job = await job_service.get_job(job_id, current_user.id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    if job.status != JobStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Can only retry failed jobs, current status is {job.status.value}",
        )

    # Reset job for retry
    from datetime import datetime, timezone
    from app.core.arq_config import enqueue_job
    from app.schemas.generation_job import GenerationRequest
    import uuid

    # Generate new ARQ job ID for retry
    new_arq_job_id = f"gen-{uuid.uuid4().hex[:12]}"

    job.arq_job_id = new_arq_job_id
    job.status = JobStatus.PENDING
    job.retry_count += 1
    job.error_msg = None
    job.error_code = None
    job.next_retry_at = None
    job.progress_pct = 0.0
    job.progress_message = "Manual retry queued"
    job.started_at = None
    job.completed_at = None

    await db.commit()
    await db.refresh(job)

    # Re-enqueue job
    request = GenerationRequest(
        job_id=job.id,
        arq_job_id=new_arq_job_id,
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
            _job_id=new_arq_job_id,
        )
        logger.info(f"Manually retried job {job_id} with new ARQ ID {new_arq_job_id}")
    except Exception as e:
        job.status = JobStatus.FAILED
        job.error_msg = f"Failed to enqueue retry: {str(e)}"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enqueue retry: {str(e)}",
        )

    # Get queue info for response
    result = await job_service.get_job_with_queue_info(job.id, current_user.id)
    job, queue_info = result

    return GenerationJobResponse(
        id=job.id,
        arq_job_id=job.arq_job_id,
        status=job.status,
        progress_pct=job.progress_pct,
        progress_message=job.progress_message,
        queue_position=queue_info.queue_position if queue_info else None,
        estimated_wait_seconds=queue_info.estimated_wait_seconds if queue_info else None,
        document_id=str(job.document_id) if job.document_id else None,
        retry_count=job.retry_count,
        max_retries=job.max_retries,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        cancelled_at=job.cancelled_at,
    )
