"""Redis Pub/Sub manager for real-time progress broadcasting.

This module provides a centralized pub/sub system for broadcasting job progress
events across multiple workers and WebSocket connections. It uses Redis pub/sub
to ensure events are delivered to all interested subscribers regardless of which
worker is processing the job.

Architecture:
- Workers publish progress events to job-specific channels
- WebSocket handlers subscribe to channels for jobs they're monitoring
- Redis acts as the message broker for multi-worker coordination

Usage:
    # Publishing (from worker)
    await pubsub_manager.publish_progress(job_id, event)

    # Subscribing (from WebSocket handler)
    async for message in pubsub_manager.subscribe(job_id):
        await websocket.send_json(message)
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import AsyncGenerator, Optional

import redis.asyncio as redis

from app.core.config import settings
from app.core.redis import redis_conn
from app.models.generation_job import JobStatus
from app.schemas.websocket import (
    BaseWebSocketEvent,
    JobCompletedEvent,
    JobFailedEvent,
    JobStartedEvent,
    ProgressUpdateEvent,
    WebSocketEventType,
    WebSocketMessage,
)

logger = logging.getLogger(__name__)


def get_job_channel(job_id: int) -> str:
    """Get the Redis pub/sub channel name for a job.

    Args:
        job_id: The job ID

    Returns:
        Channel name in format "job:progress:{job_id}"
    """
    return f"job:progress:{job_id}"


class PubSubManager:
    """Manager for Redis pub/sub operations for job progress updates.

    This class handles:
    - Publishing progress events from workers
    - Subscribing to job channels from WebSocket handlers
    - Connection pooling and error recovery
    - Message serialization/deserialization
    """

    def __init__(self):
        """Initialize the pub/sub manager."""
        self._pubsub_clients: dict[int, redis.client.PubSub] = {}

    async def get_client(self) -> redis.Redis:
        """Get Redis client for publishing.

        Returns:
            Redis client instance
        """
        return await redis_conn.get_client()

    async def publish_event(
        self,
        job_id: int,
        event: BaseWebSocketEvent,
        correlation_id: Optional[str] = None,
    ) -> int:
        """Publish an event to a job's channel.

        Args:
            job_id: Job ID to publish to
            event: Event to publish
            correlation_id: Optional correlation ID for tracking

        Returns:
            Number of subscribers that received the message

        Raises:
            Exception: If publishing fails
        """
        channel = get_job_channel(job_id)
        message = WebSocketMessage.from_event(event, correlation_id)

        try:
            client = await self.get_client()
            result = await client.publish(channel, message.model_dump_json())
            logger.debug(f"Published {event.type.value} to {channel}, {result} subscribers")
            return result
        except Exception as e:
            logger.error(f"Failed to publish event to {channel}: {e}")
            raise

    async def publish_job_started(
        self,
        job_id: int,
        started_at: datetime,
        agent_name: Optional[str] = None,
    ) -> int:
        """Publish a job started event.

        Args:
            job_id: Job ID
            started_at: When the job started
            agent_name: First agent to process (optional)

        Returns:
            Number of subscribers notified
        """
        event = JobStartedEvent(
            job_id=job_id,
            started_at=started_at,
            agent_name=agent_name,
        )
        return await self.publish_event(job_id, event)

    async def publish_progress(
        self,
        job_id: int,
        progress_pct: float,
        progress_message: Optional[str] = None,
        agent_name: Optional[str] = None,
        stage: Optional[str] = None,
    ) -> int:
        """Publish a progress update event.

        Args:
            job_id: Job ID
            progress_pct: Progress percentage (0-100)
            progress_message: Human-readable status message
            agent_name: Current processing agent
            stage: Current stage within the agent

        Returns:
            Number of subscribers notified
        """
        event = ProgressUpdateEvent(
            job_id=job_id,
            progress_pct=progress_pct,
            progress_message=progress_message,
            agent_name=agent_name,
            stage=stage,
        )
        return await self.publish_event(job_id, event)

    async def publish_job_completed(
        self,
        job_id: int,
        completed_at: datetime,
        map_id: Optional[int] = None,
        total_duration_seconds: Optional[float] = None,
    ) -> int:
        """Publish a job completed event.

        Args:
            job_id: Job ID
            completed_at: When the job completed
            map_id: Generated map ID (if applicable)
            total_duration_seconds: Total processing time

        Returns:
            Number of subscribers notified
        """
        event = JobCompletedEvent(
            job_id=job_id,
            completed_at=completed_at,
            map_id=map_id,
            total_duration_seconds=total_duration_seconds,
        )
        return await self.publish_event(job_id, event)

    async def publish_job_failed(
        self,
        job_id: int,
        error_message: str,
        failed_at: datetime,
        error_code: Optional[str] = None,
        can_retry: bool = False,
        retry_count: int = 0,
        max_retries: int = 3,
    ) -> int:
        """Publish a job failed event.

        Args:
            job_id: Job ID
            error_message: Error description
            failed_at: When the failure occurred
            error_code: Error classification code
            can_retry: Whether the job can be retried
            retry_count: Number of retries already attempted
            max_retries: Maximum retries allowed

        Returns:
            Number of subscribers notified
        """
        event = JobFailedEvent(
            job_id=job_id,
            error_message=error_message,
            error_code=error_code,
            can_retry=can_retry,
            retry_count=retry_count,
            max_retries=max_retries,
            failed_at=failed_at,
        )
        return await self.publish_event(job_id, event)

    async def subscribe(
        self, job_id: int, timeout: float = 0.1
    ) -> AsyncGenerator[dict, None]:
        """Subscribe to a job's progress channel.

        This is an async generator that yields messages as they arrive.
        It handles connection management and cleanup automatically.

        Args:
            job_id: Job ID to subscribe to
            timeout: Timeout in seconds for each message check

        Yields:
            Parsed message dictionaries

        Example:
            async for message in pubsub_manager.subscribe(job_id):
                await websocket.send_json(message)
        """
        channel = get_job_channel(job_id)
        client = await self.get_client()
        pubsub = client.pubsub()

        try:
            await pubsub.subscribe(channel)
            logger.info(f"Subscribed to channel: {channel}")

            while True:
                try:
                    message = await asyncio.wait_for(
                        pubsub.get_message(ignore_subscribe_messages=True),
                        timeout=timeout,
                    )

                    if message is not None and message["type"] == "message":
                        data = message["data"]
                        # Handle both string and bytes
                        if isinstance(data, bytes):
                            data = data.decode("utf-8")
                        parsed = json.loads(data)
                        yield parsed

                except asyncio.TimeoutError:
                    # No message received, continue waiting
                    # Yield None to allow caller to check if connection is still alive
                    yield None

                except asyncio.CancelledError:
                    logger.info(f"Subscription to {channel} cancelled")
                    break

        except Exception as e:
            logger.error(f"Error in subscription to {channel}: {e}")
            raise

        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
            logger.info(f"Unsubscribed from channel: {channel}")

    async def get_subscriber(self, job_id: int) -> redis.client.PubSub:
        """Get a pubsub subscriber for a job channel.

        This method creates a new pubsub instance that the caller
        must manage and close.

        Args:
            job_id: Job ID to subscribe to

        Returns:
            PubSub instance subscribed to the job channel
        """
        channel = get_job_channel(job_id)
        client = await self.get_client()
        pubsub = client.pubsub()
        await pubsub.subscribe(channel)
        return pubsub


# Global pub/sub manager instance
pubsub_manager = PubSubManager()


async def get_pubsub_manager() -> PubSubManager:
    """Dependency for FastAPI routes to get pub/sub manager.

    Returns:
        PubSubManager instance
    """
    return pubsub_manager
