"""ARQ (Async Redis Queue) configuration for job processing.

This module provides the configuration for ARQ workers and job enqueueing.
It replaces the RabbitMQ-based queue with a Redis-based async queue.
"""

from typing import Any, Optional
from dataclasses import dataclass
from datetime import timedelta
import logging

from arq import create_pool
from arq.connections import RedisSettings, ArqRedis
from arq.jobs import Job

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class RetryConfig:
    """Configuration for job retry behavior with exponential backoff."""

    max_retries: int = 3
    base_delay_seconds: int = 5
    max_delay_seconds: int = 300  # 5 minutes max
    exponential_base: float = 2.0

    def get_delay(self, attempt: int) -> int:
        """Calculate delay for a given retry attempt using exponential backoff.

        Args:
            attempt: Current retry attempt (0-indexed)

        Returns:
            Delay in seconds before next retry
        """
        delay = self.base_delay_seconds * (self.exponential_base ** attempt)
        return min(int(delay), self.max_delay_seconds)


# Default retry configuration
DEFAULT_RETRY_CONFIG = RetryConfig()


def parse_redis_url(url: str) -> RedisSettings:
    """Parse Redis URL into ARQ RedisSettings.

    Args:
        url: Redis URL in format redis://:password@host:port/db

    Returns:
        RedisSettings configured for ARQ
    """
    # Handle URL with password format: redis://:password@host:port/db
    # or without password: redis://host:port/db
    import re

    pattern = r'redis://(?::([^@]+)@)?([^:]+):(\d+)(?:/(\d+))?'
    match = re.match(pattern, url)

    if not match:
        raise ValueError(f"Invalid Redis URL format: {url}")

    password = match.group(1)
    host = match.group(2)
    port = int(match.group(3))
    database = int(match.group(4)) if match.group(4) else 0

    return RedisSettings(
        host=host,
        port=port,
        password=password,
        database=database,
    )


def get_redis_settings() -> RedisSettings:
    """Get ARQ Redis settings from application config."""
    return parse_redis_url(settings.REDIS_URL)


# ARQ Worker Settings
class WorkerSettings:
    """ARQ Worker configuration.

    This class is discovered by the ARQ CLI when starting workers.
    Usage: arq app.core.arq_config.WorkerSettings
    """

    # Redis connection settings
    redis_settings = get_redis_settings()

    # Queue names
    queue_name = "overworld:jobs"

    # Worker behavior
    max_jobs = 10  # Maximum concurrent jobs
    job_timeout = 600  # 10 minutes max per job
    max_tries = 1  # We handle retries manually for better control
    poll_delay = 0.5  # Seconds between polling for jobs

    # Health check
    health_check_interval = 30  # Seconds

    # Functions registered for this worker (imported at runtime to avoid circular imports)
    @staticmethod
    def get_functions():
        """Get list of worker functions.

        Note: This is called at worker startup to register task functions.
        """
        from app.workers.arq_tasks import (
            process_generation_job,
            update_job_progress,
            cleanup_stale_jobs,
        )
        return [
            process_generation_job,
            update_job_progress,
            cleanup_stale_jobs,
        ]

    functions = property(lambda self: WorkerSettings.get_functions())

    # Cron jobs for maintenance
    cron_jobs = []  # Will add cleanup_stale_jobs as cron if needed


# Global ARQ pool for enqueueing jobs
_arq_pool: Optional[ArqRedis] = None


async def get_arq_pool() -> ArqRedis:
    """Get or create the global ARQ Redis pool.

    Returns:
        ArqRedis connection pool for enqueueing jobs
    """
    global _arq_pool
    if _arq_pool is None:
        _arq_pool = await create_pool(get_redis_settings())
    return _arq_pool


async def close_arq_pool() -> None:
    """Close the global ARQ Redis pool."""
    global _arq_pool
    if _arq_pool is not None:
        await _arq_pool.close()
        _arq_pool = None


async def enqueue_job(
    function_name: str,
    *args: Any,
    _job_id: Optional[str] = None,
    _queue_name: Optional[str] = None,
    _defer_until: Optional[Any] = None,
    _defer_by: Optional[timedelta] = None,
    _expires: Optional[timedelta] = None,
    **kwargs: Any,
) -> Optional[Job]:
    """Enqueue a job to the ARQ queue.

    Args:
        function_name: Name of the function to execute
        *args: Positional arguments for the function
        _job_id: Optional custom job ID (for deduplication)
        _queue_name: Optional queue name override
        _defer_until: Datetime to defer execution until
        _defer_by: Timedelta to defer execution by
        _expires: Timedelta after which job expires if not executed
        **kwargs: Keyword arguments for the function

    Returns:
        Job object if enqueued, None if duplicate job ID exists
    """
    pool = await get_arq_pool()

    try:
        job = await pool.enqueue_job(
            function_name,
            *args,
            _job_id=_job_id,
            _queue_name=_queue_name or WorkerSettings.queue_name,
            _defer_until=_defer_until,
            _defer_by=_defer_by,
            _expires=_expires,
            **kwargs,
        )

        if job is None:
            logger.warning(f"Job with ID {_job_id} already exists, skipping")
        else:
            logger.info(f"Enqueued job {function_name} with ID {job.job_id}")

        return job

    except Exception as e:
        logger.error(f"Failed to enqueue job {function_name}: {e}")
        raise


async def get_job_result(job_id: str, timeout: float = 0) -> Any:
    """Get the result of a completed job.

    Args:
        job_id: The job ID to get result for
        timeout: Seconds to wait for result (0 = don't wait)

    Returns:
        Job result if available
    """
    pool = await get_arq_pool()
    job = Job(job_id=job_id, redis=pool)

    if timeout > 0:
        return await job.result(timeout=timeout)

    return await job.result(timeout=0)


async def abort_job(job_id: str) -> bool:
    """Attempt to abort a queued or running job.

    Args:
        job_id: The job ID to abort

    Returns:
        True if abort signal was sent, False otherwise
    """
    pool = await get_arq_pool()
    job = Job(job_id=job_id, redis=pool)

    try:
        await job.abort()
        logger.info(f"Sent abort signal to job {job_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to abort job {job_id}: {e}")
        return False


async def get_job_status(job_id: str) -> Optional[dict]:
    """Get the status of a job from ARQ.

    Args:
        job_id: The job ID to check

    Returns:
        Dict with job status info, or None if job not found
    """
    pool = await get_arq_pool()
    job = Job(job_id=job_id, redis=pool)

    try:
        status = await job.status()
        info = await job.info()

        return {
            "job_id": job_id,
            "status": status.value if status else "unknown",
            "info": info,
        }
    except Exception as e:
        logger.error(f"Failed to get job status for {job_id}: {e}")
        return None
