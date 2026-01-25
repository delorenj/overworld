"""FastAPI application entry point.

This module configures the FastAPI application with:
- CORS middleware for frontend communication
- API v1 router with all endpoints
- Redis/ARQ lifecycle management
- Health check endpoints
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.redis import init_redis, close_redis
from app.core.arq_config import get_arq_pool, close_arq_pool

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown events.

    Handles:
    - Redis connection pool initialization
    - ARQ job queue pool initialization
    - Graceful shutdown of connections
    """
    # Startup
    logger.info("Starting Overworld API...")

    try:
        # Initialize Redis connection pool
        await init_redis()
        logger.info("Redis connection pool initialized")

        # Initialize ARQ pool for job enqueueing
        await get_arq_pool()
        logger.info("ARQ job queue pool initialized")

    except Exception as e:
        logger.error(f"Failed to initialize connections: {e}")
        # Continue startup even if Redis is unavailable
        # Jobs will fail gracefully

    yield  # Application is running

    # Shutdown
    logger.info("Shutting down Overworld API...")

    try:
        # Close ARQ pool
        await close_arq_pool()
        logger.info("ARQ pool closed")

        # Close Redis connection pool
        await close_redis()
        logger.info("Redis connection pool closed")

    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


app = FastAPI(
    title="Overworld API",
    description="AI-powered project mapping platform with async job queue",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:5173",
        "http://localhost:8001",
        "https://overworld.delo.sh",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API v1 router
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/api/health")
async def health_check():
    """Health check endpoint.

    Returns basic health status. For detailed checks including
    Redis/DB connectivity, use /api/v1/status.
    """
    return {"status": "ok", "service": "overworld-backend"}


@app.get("/api/v1/status")
async def status_check():
    """API status endpoint with service health details.

    Returns status of the API and connected services.
    """
    # Check Redis connectivity
    redis_status = "unknown"
    try:
        from app.core.redis import redis_conn
        if await redis_conn.ping():
            redis_status = "connected"
        else:
            redis_status = "disconnected"
    except Exception as e:
        redis_status = f"error: {str(e)}"

    return {
        "status": "running",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "services": {
            "redis": redis_status,
            "job_queue": "arq",
        },
    }
