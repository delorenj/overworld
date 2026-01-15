"""Tests for generation job API and worker."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.api.v1.routers.generation import router
from app.models.generation_job import JobStatus
from app.models.user import User
from app.schemas.generation_job import GenerationJobCreate


@pytest.mark.asyncio
async def test_create_generation_job_success(async_client: AsyncClient, test_user: User):
    """Test successful generation job creation."""

    job_data = GenerationJobCreate(
        document_id=str(uuid4()),
        theme_id="smb3",
        options={"scatter_threshold": 0.8},
    )

    with patch("app.api.v1.routers.generation.get_queue_position") as mock_queue:
        mock_queue.return_value = MagicMock(queue_position=1, estimated_wait_seconds=30)

        with patch("app.api.v1.routers.generation.rabbitmq") as mock_rabbitmq:
            response = await async_client.post(
                "/api/v1/maps/generate",
                json=job_data.dict(),
            )

    assert response.status_code == 202

    data = response.json()
    assert data["status"] == JobStatus.PENDING.value
    assert data["queue_position"] == 1
    assert data["estimated_wait_seconds"] == 30
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_generation_job_invalid_document(async_client: AsyncClient, test_user: User):
    """Test generation job creation with invalid document ID."""

    job_data = GenerationJobCreate(
        document_id="invalid-uuid",
        theme_id="smb3",
    )

    response = await async_client.post(
        "/api/v1/maps/generate",
        json=job_data.dict(),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_job_status_success(async_client: AsyncClient, test_user: User):
    """Test successful job status retrieval."""

    with patch("app.api.v1.routers.generation.get_queue_position") as mock_queue:
        mock_queue.return_value = MagicMock(queue_position=1, estimated_wait_seconds=30)

        response = await async_client.get("/api/v1/jobs/1")

    assert response.status_code == 200

    data = response.json()
    assert "id" in data
    assert "status" in data
    assert "progress_pct" in data


@pytest.mark.asyncio
async def test_get_job_status_not_found(async_client: AsyncClient, test_user: User):
    """Test job status retrieval for non-existent job."""

    response = await async_client.get("/api/v1/jobs/999")

    assert response.status_code == 404
    assert "Generation job not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_user_jobs(async_client: AsyncClient, test_user: User):
    """Test listing user's generation jobs."""

    response = await async_client.get("/api/v1/jobs")

    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_generation_worker_timeout():
    """Test worker timeout handling."""
    from app.workers.generation_worker import GenerationWorker

    worker = GenerationWorker()

    with patch("app.workers.generation_worker.DocumentProcessor") as mock_processor:
        mock_processor.return_value.process_document.side_effect = lambda x: (asyncio.sleep(130))

        request = MagicMock()
        request.job_id = 1
        request.document_id = str(uuid4())
        request.user_id = 1
        request.theme_id = "smb3"
        request.options = {}

        with pytest.raises(asyncio.TimeoutError):
            await worker._process_job(request)


@pytest.mark.asyncio
async def test_job_state_transitions():
    """Test job state machine transitions."""
    from app.workers.generation_worker import GenerationWorker
    from app.core.database import get_async_session

    worker = GenerationWorker()

    async with get_async_session() as db:
        await worker._update_job_status(db, 1, JobStatus.PROCESSING, 0.0)
        await worker._update_job_status(db, 1, JobStatus.COMPLETED, 100.0)
        await worker._update_job_status(db, 2, JobStatus.FAILED, 0.0, "Test error")


@pytest.mark.asyncio
async def test_transient_error_detection():
    """Test transient vs permanent error classification."""
    from app.workers.generation_worker import GenerationWorker

    worker = GenerationWorker()

    assert worker._is_transient_error("Network timeout occurred")
    assert worker._is_transient_error("API rate limit exceeded")
    assert worker._is_transient_error("Temporary connection failure")

    assert not worker._is_transient_error("Invalid document format")
    assert not worker._is_transient_error("Document not found")
    assert not worker._is_transient_error("Parse error: malformed content")
