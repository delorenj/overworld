"""API routes for generation job management."""

import json
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_rabbitmq
from app.core.queue import QueueConfig, rabbitmq
from app.models.generation_job import GenerationJob, JobStatus
from app.models.user import User
from app.schemas.generation_job import (
    GenerationJobCreate,
    GenerationJobResponse,
    JobQueueInfo,
    GenerationRequest,
)

router = APIRouter()


@router.post(
    "/maps/generate", status_code=status.HTTP_202_ACCEPTED, response_model=GenerationJobResponse
)
async def create_generation_job(
    job_data: GenerationJobCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    rabbitmq_conn=Depends(get_rabbitmq),
) -> Dict[str, Any]:
    """Create a new map generation job and queue it for processing."""

    generation_job = GenerationJob(
        document_id=job_data.document_id,
        user_id=current_user.id,
        status=JobStatus.PENDING,
        options=job_data.options,
    )

    db.add(generation_job)
    await db.commit()
    await db.refresh(generation_job)

    queue_info = await get_queue_position(db, generation_job.id)

    message = GenerationRequest(
        job_id=generation_job.id,
        document_id=job_data.document_id,
        user_id=current_user.id,
        theme_id=job_data.theme_id,
        options=job_data.options or {},
    )

    await rabbitmq_conn.publish_message(
        routing_key=QueueConfig.ROUTING_KEY_PENDING,
        message=json.dumps(message.dict()).encode(),
    )

    return GenerationJobResponse(
        id=generation_job.id,
        status=generation_job.status,
        progress_pct=generation_job.progress_pct,
        queue_position=queue_info.queue_position,
        estimated_wait_seconds=queue_info.estimated_wait_seconds,
        created_at=generation_job.created_at,
        started_at=generation_job.started_at,
        completed_at=generation_job.completed_at,
    )


@router.get("/jobs/{job_id}", response_model=GenerationJobResponse)
async def get_job_status(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GenerationJobResponse:
    """Get status and details of a generation job."""

    stmt = select(GenerationJob).where(
        GenerationJob.id == job_id,
        GenerationJob.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generation job not found",
        )

    queue_position = None
    estimated_wait_seconds = None
    if job.status == JobStatus.PENDING:
        queue_info = await get_queue_position(db, job.id)
        queue_position = queue_info.queue_position
        estimated_wait_seconds = queue_info.estimated_wait_seconds

    return GenerationJobResponse(
        id=job.id,
        status=job.status,
        progress_pct=job.progress_pct,
        queue_position=queue_position,
        estimated_wait_seconds=estimated_wait_seconds,
        map_id=job.map_id,
        error_msg=job.error_msg,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


@router.get("/jobs", response_model=list[GenerationJobResponse])
async def list_user_jobs(
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    status_filter: JobStatus = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[GenerationJobResponse]:
    """List generation jobs for the current user."""

    stmt = select(GenerationJob).where(GenerationJob.user_id == current_user.id)

    if status_filter:
        stmt = stmt.where(GenerationJob.status == status_filter)

    stmt = stmt.order_by(GenerationJob.created_at.desc()).offset(offset).limit(limit)

    result = await db.execute(stmt)
    jobs = result.scalars().all()

    return [
        GenerationJobResponse(
            id=job.id,
            status=job.status,
            progress_pct=job.progress_pct,
            map_id=job.map_id,
            error_msg=job.error_msg,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
        )
        for job in jobs
    ]


async def get_queue_position(db: AsyncSession, job_id: int) -> JobQueueInfo:
    """Get queue position and estimated wait time for a job."""

    stmt = select(GenerationJob).where(
        GenerationJob.status == JobStatus.PENDING,
        GenerationJob.created_at
        < (select(GenerationJob.created_at).where(GenerationJob.id == job_id).scalar_subquery()),
    )
    result = await db.execute(stmt)
    jobs_ahead = len(result.scalars().all())

    queue_position = jobs_ahead + 1
    estimated_wait_seconds = jobs_ahead * 30

    return JobQueueInfo(
        queue_position=queue_position,
        estimated_wait_seconds=estimated_wait_seconds,
        jobs_ahead=jobs_ahead,
    )
