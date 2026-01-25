"""WebSocket endpoint for real-time job progress updates.

This module provides a WebSocket endpoint for clients to receive real-time
progress updates for their generation jobs. It supports:

- JWT authentication via query parameter
- Automatic subscription to job progress events
- Connection lifecycle management
- Ping/pong heartbeat for connection health
- Error handling and graceful disconnection

Usage:
    ws://localhost:8000/api/v1/ws/jobs/{job_id}?token={jwt_token}
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.core.pubsub import pubsub_manager
from app.models.generation_job import GenerationJob, JobStatus
from app.schemas.websocket import (
    ConnectionErrorEvent,
    ConnectionEstablishedEvent,
    PingEvent,
    PongEvent,
    WebSocketEventType,
    WebSocketMessage,
)
from app.services.auth_service import AuthService, InvalidTokenError, TokenRevokedError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket"])


class WebSocketConnectionManager:
    """Manages WebSocket connections for job progress updates."""

    def __init__(self):
        """Initialize the connection manager."""
        # Track active connections: job_id -> list of websockets
        self.active_connections: dict[int, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, job_id: int) -> None:
        """Accept a WebSocket connection and add it to tracking.

        Args:
            websocket: The WebSocket instance
            job_id: The job ID being monitored
        """
        await websocket.accept()

        if job_id not in self.active_connections:
            self.active_connections[job_id] = []
        self.active_connections[job_id].append(websocket)

        logger.info(
            f"WebSocket connected for job {job_id}, "
            f"total connections: {len(self.active_connections[job_id])}"
        )

    def disconnect(self, websocket: WebSocket, job_id: int) -> None:
        """Remove a WebSocket connection from tracking.

        Args:
            websocket: The WebSocket instance
            job_id: The job ID that was being monitored
        """
        if job_id in self.active_connections:
            if websocket in self.active_connections[job_id]:
                self.active_connections[job_id].remove(websocket)

            # Clean up empty lists
            if not self.active_connections[job_id]:
                del self.active_connections[job_id]

        logger.info(f"WebSocket disconnected for job {job_id}")

    async def send_event(self, websocket: WebSocket, event: dict) -> bool:
        """Send an event to a WebSocket connection.

        Args:
            websocket: The WebSocket instance
            event: The event dictionary to send

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            await websocket.send_json(event)
            return True
        except Exception as e:
            logger.error(f"Failed to send event: {e}")
            return False

    def get_connection_count(self, job_id: int) -> int:
        """Get the number of active connections for a job.

        Args:
            job_id: The job ID

        Returns:
            Number of active connections
        """
        return len(self.active_connections.get(job_id, []))


# Global connection manager
connection_manager = WebSocketConnectionManager()


async def authenticate_websocket(
    token: Optional[str], db: AsyncSession
) -> tuple[bool, Optional[int], Optional[str]]:
    """Authenticate a WebSocket connection using JWT token.

    Args:
        token: JWT token from query parameter
        db: Database session

    Returns:
        Tuple of (is_valid, user_id, error_message)
    """
    if not token:
        return False, None, "Missing authentication token"

    auth_service = AuthService(db)

    try:
        user = await auth_service.validate_access_token(token)
        return True, user.id, None
    except TokenRevokedError:
        return False, None, "Token has been revoked"
    except InvalidTokenError:
        return False, None, "Invalid or expired token"
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        return False, None, "Authentication failed"


async def verify_job_access(
    job_id: int, user_id: int, db: AsyncSession
) -> tuple[bool, Optional[GenerationJob], Optional[str]]:
    """Verify the user has access to the specified job.

    Args:
        job_id: Job ID to verify
        user_id: User ID to check ownership
        db: Database session

    Returns:
        Tuple of (has_access, job, error_message)
    """
    stmt = select(GenerationJob).where(
        GenerationJob.id == job_id,
        GenerationJob.user_id == user_id,
    )
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()

    if job is None:
        return False, None, "Job not found or access denied"

    return True, job, None


@router.websocket("/jobs/{job_id}")
async def websocket_job_progress(
    websocket: WebSocket,
    job_id: int,
    token: Optional[str] = Query(None, description="JWT authentication token"),
):
    """WebSocket endpoint for real-time job progress updates.

    Clients connect to this endpoint to receive real-time updates about
    their generation job progress. Authentication is done via JWT token
    in the query string.

    Connection Flow:
    1. Client connects with JWT token
    2. Server validates token and job ownership
    3. Server sends connection_established event with current job state
    4. Server forwards progress events from Redis pub/sub
    5. Connection closes when job completes/fails or client disconnects

    Args:
        websocket: WebSocket connection
        job_id: ID of the job to monitor
        token: JWT authentication token (query parameter)

    Message Types Received:
    - ping: Client heartbeat, server responds with pong

    Message Types Sent:
    - connection_established: Initial connection acknowledgment
    - connection_error: Authentication or access errors
    - job_started: Job has started processing
    - progress_update: Progress percentage and status
    - job_completed: Job finished successfully
    - job_failed: Job failed with error
    - pong: Response to client ping
    """
    # Get database session
    async with get_async_session() as db:
        # Authenticate the connection
        is_valid, user_id, error_msg = await authenticate_websocket(token, db)

        if not is_valid:
            # Accept connection just to send error, then close
            await websocket.accept()
            error_event = ConnectionErrorEvent(
                error_code="AUTH_FAILED",
                message=error_msg or "Authentication failed",
            )
            await websocket.send_json(
                WebSocketMessage.from_event(error_event).model_dump(mode="json")
            )
            await websocket.close(code=4001, reason=error_msg)
            return

        # Verify job access
        has_access, job, access_error = await verify_job_access(job_id, user_id, db)

        if not has_access:
            await websocket.accept()
            error_event = ConnectionErrorEvent(
                error_code="ACCESS_DENIED",
                message=access_error or "Access denied",
            )
            await websocket.send_json(
                WebSocketMessage.from_event(error_event).model_dump(mode="json")
            )
            await websocket.close(code=4003, reason=access_error)
            return

        # Accept connection and add to tracking
        await connection_manager.connect(websocket, job_id)

        try:
            # Send initial connection established event
            established_event = ConnectionEstablishedEvent(
                job_id=job_id,
                current_status=job.status,
                current_progress=job.progress_pct,
                message=f"Connected to job {job_id} progress stream",
            )
            await websocket.send_json(
                WebSocketMessage.from_event(established_event).model_dump(mode="json")
            )

            # If job is already in terminal state, notify and keep connection open briefly
            if job.is_terminal:
                logger.info(f"Job {job_id} is already in terminal state: {job.status}")
                # Connection established, client can now close if desired

            # Start listening for progress updates and client messages
            await handle_websocket_session(websocket, job_id, job)

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for job {job_id}")

        except Exception as e:
            logger.error(f"WebSocket error for job {job_id}: {e}")
            try:
                error_event = ConnectionErrorEvent(
                    error_code="INTERNAL_ERROR",
                    message="Internal server error",
                )
                await websocket.send_json(
                    WebSocketMessage.from_event(error_event).model_dump(mode="json")
                )
            except Exception:
                pass

        finally:
            connection_manager.disconnect(websocket, job_id)


async def handle_websocket_session(
    websocket: WebSocket, job_id: int, job: GenerationJob
) -> None:
    """Handle the main WebSocket session loop.

    This function manages:
    - Subscribing to Redis pub/sub for job events
    - Handling client messages (ping/pong)
    - Forwarding progress events to the client
    - Detecting disconnection

    Args:
        websocket: The WebSocket connection
        job_id: The job ID being monitored
        job: The job database record
    """
    # Create tasks for handling both directions
    receive_task = asyncio.create_task(handle_client_messages(websocket, job_id))
    pubsub_task = asyncio.create_task(handle_pubsub_messages(websocket, job_id))

    try:
        # Wait for either task to complete (e.g., disconnect or job completion)
        done, pending = await asyncio.wait(
            [receive_task, pubsub_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Cancel remaining tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    except asyncio.CancelledError:
        receive_task.cancel()
        pubsub_task.cancel()


async def handle_client_messages(websocket: WebSocket, job_id: int) -> None:
    """Handle incoming messages from the WebSocket client.

    Processes:
    - ping: Responds with pong for connection keep-alive

    Args:
        websocket: The WebSocket connection
        job_id: The job ID being monitored
    """
    try:
        while True:
            # Wait for client message
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                event_type = message.get("event", {}).get("type")

                if event_type == WebSocketEventType.PING.value:
                    # Respond with pong
                    pong_event = PongEvent()
                    await websocket.send_json(
                        WebSocketMessage.from_event(pong_event).model_dump(mode="json")
                    )
                    logger.debug(f"Sent pong to client for job {job_id}")

            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON from client for job {job_id}")

    except WebSocketDisconnect:
        logger.info(f"Client disconnected from job {job_id}")
        raise

    except Exception as e:
        logger.error(f"Error handling client messages for job {job_id}: {e}")
        raise


async def handle_pubsub_messages(websocket: WebSocket, job_id: int) -> None:
    """Handle messages from Redis pub/sub and forward to WebSocket.

    Args:
        websocket: The WebSocket connection
        job_id: The job ID being monitored
    """
    try:
        async for message in pubsub_manager.subscribe(job_id, timeout=1.0):
            if message is not None:
                # Forward the message to the WebSocket client
                await websocket.send_json(message)

                # Check if this is a terminal event
                event_type = message.get("event", {}).get("type")
                if event_type in [
                    WebSocketEventType.JOB_COMPLETED.value,
                    WebSocketEventType.JOB_FAILED.value,
                    WebSocketEventType.JOB_CANCELLED.value,
                ]:
                    logger.info(
                        f"Job {job_id} reached terminal state via pub/sub: {event_type}"
                    )
                    # Keep connection open briefly for client to process
                    await asyncio.sleep(0.5)
                    return

    except asyncio.CancelledError:
        logger.info(f"Pub/sub handler cancelled for job {job_id}")
        raise

    except Exception as e:
        logger.error(f"Error in pub/sub handler for job {job_id}: {e}")
        raise
