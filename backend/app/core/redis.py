"""Redis connection pool configuration."""

from typing import Optional

import redis.asyncio as redis

from app.core.config import settings


class RedisConnection:
    """
    Redis connection pool manager.

    Provides connection pooling with configurable max connections.
    """

    def __init__(self):
        self.pool: Optional[redis.ConnectionPool] = None
        self.client: Optional[redis.Redis] = None

    async def connect(self) -> None:
        """Create Redis connection pool."""
        if self.pool is None:
            self.pool = redis.ConnectionPool.from_url(
                settings.REDIS_URL,
                max_connections=settings.REDIS_MAX_CONNECTIONS,
                decode_responses=True,  # Auto-decode bytes to strings
            )
            self.client = redis.Redis(connection_pool=self.pool)

    async def get_client(self) -> redis.Redis:
        """Get Redis client (create pool if not exists)."""
        if self.client is None:
            await self.connect()
        return self.client

    async def ping(self) -> bool:
        """Test Redis connection."""
        try:
            client = await self.get_client()
            return await client.ping()
        except Exception:
            return False

    async def close(self) -> None:
        """Close Redis connection pool."""
        if self.client:
            await self.client.close()
            self.client = None
        if self.pool:
            await self.pool.disconnect()
            self.pool = None


# Global Redis connection instance
redis_conn = RedisConnection()


async def get_redis() -> redis.Redis:
    """
    Dependency for FastAPI routes to get Redis client.

    Usage:
        @app.get("/cache")
        async def get_cache(redis: Redis = Depends(get_redis)):
            value = await redis.get("key")
            ...
    """
    return await redis_conn.get_client()


async def init_redis() -> None:
    """Initialize Redis connection pool (run on startup)."""
    await redis_conn.connect()


async def close_redis() -> None:
    """Close Redis connection pool (run on shutdown)."""
    await redis_conn.close()
