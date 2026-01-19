"""Background worker for processing generation jobs."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.core.queue import QueueConfig, rabbitmq
from app.models.generation_job import GenerationJob, JobStatus
from app.models.user import User
from app.services.document_processor import DocumentProcessor
from app.schemas.generation_job import GenerationRequest, JobStateUpdate


logger = logging.getLogger(__name__)

class GenerationWorker:
    """Background worker for processing generation jobs."""

    def __init__(self):
        self.processing = False
        self.current_job_id: Optional[int] = None

    async def start(self) -> None:
        """Start the worker and begin consuming jobs."""
        await rabbitmq.setup_topology()
        logger.info("Generation worker started")

        while self.processing:
            try:
                await rabbitmq.connect()
                channel = rabbitmq.channel

                channel.basic_qos(prefetch_count=1)
                channel.basic_consume(
                    queue=QueueConfig.QUEUE_PENDING,
                    on_message_callback=self._handle_message,
                    auto_ack=False,
                )

                logger.info("Waiting for messages...")
                channel.start_consuming()

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
            logger.error(f"Job {request.job_id} failed: {e}")
            await self._handle_failure(request, str(e))
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

     async def _process_job(self, request: GenerationRequest) -> None:
        """Process a single generation job."""
        async with get_async_session() as db:
            await self._update_job_status(db, request.job_id, JobStatus.PROCESSING, 0.0)
                
                context = JobContext(
                    job_id=request.job_id,
                    user_id=request.user_id,
                    document_url=f"",
                    hierarchy={"L0": {"title": "Generated Map", "id": "root"}},
                    theme=request.theme_id or "smb3",
                    options=request.options,
                )
                
                coordinator = CoordinatorAgent()
                result = await coordinator.execute(context)
                
                if result.success and result.data:
                    await self._update_job_status(db, request.job_id, JobStatus.COMPLETED, 100.0)
                    logger.info(f"Job {request.job_id}: Map generated successfully")
                else:
                    await self._update_job_status(db, request.job_id, JobStatus.FAILED, 0.0, result.error if result.error else "Generation failed")
                
            except Exception as e:
                await self._update_job_status(db, request.job_id, JobStatus.FAILED, 0.0, str(e))

    async def _update_job_status(
        self,
        db: AsyncSession,
        job_id: int,
        status: JobStatus,
        progress: float,
        error_msg: Optional[str] = None,
    ) -> None:
        """Update job status in database."""
        stmt = select(GenerationJob).where(GenerationJob.id == job_id)
        result = await db.execute(stmt)
        job = result.scalar_one()

        job.status = status
        job.progress_pct = progress
        job.error_msg = error_msg

        if status == JobStatus.PROCESSING and not job.started_at:
            job.started_at = datetime.utcnow()
        elif status in [JobStatus.COMPLETED, JobStatus.FAILED] and not job.completed_at:
            job.completed_at = datetime.utcnow()

        await db.commit()

        logger.info(f"Job {job_id}: {status.value} ({progress}%)")

    async def _handle_timeout(self, request: GenerationRequest) -> None:
        """Handle job timeout."""
        async with get_async_session() as db:
            await self._update_job_status(
                db,
                request.job_id,
                JobStatus.FAILED,
                0.0,
                "Generation timeout exceeded",
            )

        await rabbitmq.publish_message(
            routing_key=QueueConfig.ROUTING_KEY_FAILED,
            message=json.dumps(request.dict()).encode(),
        )

    async def _handle_failure(self, request: GenerationRequest, error: str) -> None:
        """Handle job failure."""
        async with get_async_session() as db:
            await self._update_job_status(db, request.job_id, JobStatus.FAILED, 0.0, error)

        if self._is_transient_error(error):
            await rabbitmq.publish_message(
                routing_key=QueueConfig.ROUTING_KEY_RETRY,
                message=json.dumps(request.dict()).encode(),
            )
        else:
            await rabbitmq.publish_message(
                routing_key=QueueConfig.ROUTING_KEY_FAILED,
                message=json.dumps(request.dict()).encode(),
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
