"""Rate limiting middleware for anonymous users.

This module provides:
- IP-based rate limiting for anonymous users
- Fingerprint-based rate limiting (optional)
- Redis-backed storage with automatic TTL
- Graceful degradation if Redis is unavailable
- Detailed rate limit headers (X-RateLimit-*)
"""

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, Request, status
from redis.asyncio import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)

# Rate limit keys
RATE_LIMIT_PREFIX = "ratelimit:anonymous"
RATE_LIMIT_TTL = 86400  # 24 hours in seconds


class RateLimitExceeded(HTTPException):
    """Exception raised when rate limit is exceeded."""

    def __init__(self, retry_after: int, limit: int, window: str = "24h"):
        """Initialize rate limit exception.

        Args:
            retry_after: Seconds until limit resets
            limit: Maximum allowed requests
            window: Time window (e.g., "24h")
        """
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "rate_limit_exceeded",
                "message": f"Anonymous users are limited to {limit} map generations per {window}.",
                "limit": limit,
                "window": window,
                "retry_after": retry_after,
            },
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(
                    int((datetime.now(timezone.utc) + timedelta(seconds=retry_after)).timestamp())
                ),
            },
        )


class AnonymousRateLimiter:
    """Rate limiter for anonymous user requests.

    Uses Redis to track request counts per IP address (optionally with fingerprint).
    Implements a sliding window counter with automatic expiration.
    """

    def __init__(
        self,
        redis_client: Optional[Redis] = None,
        limit: Optional[int] = None,
    ):
        """Initialize rate limiter.

        Args:
            redis_client: Redis client for storage (optional)
            limit: Maximum requests per window (defaults to settings.ANONYMOUS_DAILY_LIMIT)
        """
        self.redis = redis_client
        self.limit = limit or settings.ANONYMOUS_DAILY_LIMIT

    def _get_client_identifier(
        self,
        request: Request,
        fingerprint: Optional[str] = None,
    ) -> str:
        """Get unique identifier for a client.

        Args:
            request: FastAPI request object
            fingerprint: Optional browser fingerprint

        Returns:
            Unique identifier string (hashed for privacy)
        """
        # Get IP address from request
        # Check X-Forwarded-For header first (for proxied requests)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For can contain multiple IPs, use the first one
            ip_address = forwarded_for.split(",")[0].strip()
        else:
            # Fall back to direct connection IP
            ip_address = request.client.host if request.client else "unknown"

        # Combine IP with fingerprint if provided
        if fingerprint:
            identifier = f"{ip_address}:{fingerprint}"
        else:
            identifier = ip_address

        # Hash the identifier for privacy (don't store raw IPs)
        hashed = hashlib.sha256(identifier.encode()).hexdigest()

        return f"{RATE_LIMIT_PREFIX}:{hashed}"

    async def check_rate_limit(
        self,
        request: Request,
        fingerprint: Optional[str] = None,
    ) -> tuple[bool, int, int]:
        """Check if request is within rate limit.

        Args:
            request: FastAPI request object
            fingerprint: Optional browser fingerprint

        Returns:
            Tuple of (allowed: bool, current_count: int, remaining: int)
        """
        # If Redis is not available, allow the request (graceful degradation)
        if not self.redis:
            logger.warning("Redis not available, skipping rate limit check")
            return True, 0, self.limit

        try:
            key = self._get_client_identifier(request, fingerprint)

            # Get current count
            current_count_str = await self.redis.get(key)
            current_count = int(current_count_str) if current_count_str else 0

            # Check if limit exceeded
            if current_count >= self.limit:
                remaining = 0
                allowed = False
            else:
                remaining = self.limit - current_count
                allowed = True

            return allowed, current_count, remaining

        except Exception as e:
            # If Redis operation fails, allow the request (fail open)
            logger.error(f"Rate limit check failed: {e}")
            return True, 0, self.limit

    async def increment_usage(
        self,
        request: Request,
        fingerprint: Optional[str] = None,
    ) -> int:
        """Increment usage counter for a client.

        Args:
            request: FastAPI request object
            fingerprint: Optional browser fingerprint

        Returns:
            New count value
        """
        if not self.redis:
            logger.warning("Redis not available, skipping usage increment")
            return 0

        try:
            key = self._get_client_identifier(request, fingerprint)

            # Increment counter
            new_count = await self.redis.incr(key)

            # Set expiration on first use
            if new_count == 1:
                await self.redis.expire(key, RATE_LIMIT_TTL)

            logger.info(f"Rate limit incremented: {key} -> {new_count}/{self.limit}")

            return new_count

        except Exception as e:
            logger.error(f"Failed to increment usage: {e}")
            return 0

    async def get_ttl(
        self,
        request: Request,
        fingerprint: Optional[str] = None,
    ) -> int:
        """Get remaining TTL for rate limit key.

        Args:
            request: FastAPI request object
            fingerprint: Optional browser fingerprint

        Returns:
            TTL in seconds, or RATE_LIMIT_TTL if key doesn't exist
        """
        if not self.redis:
            return RATE_LIMIT_TTL

        try:
            key = self._get_client_identifier(request, fingerprint)
            ttl = await self.redis.ttl(key)

            # If key doesn't exist, return default TTL
            if ttl == -2:  # Key doesn't exist
                return RATE_LIMIT_TTL
            elif ttl == -1:  # Key exists but has no expiration
                await self.redis.expire(key, RATE_LIMIT_TTL)
                return RATE_LIMIT_TTL

            return ttl

        except Exception as e:
            logger.error(f"Failed to get TTL: {e}")
            return RATE_LIMIT_TTL

    async def enforce_rate_limit(
        self,
        request: Request,
        fingerprint: Optional[str] = None,
    ) -> dict:
        """Check rate limit and raise exception if exceeded.

        This is the main method to use in route dependencies.

        Args:
            request: FastAPI request object
            fingerprint: Optional browser fingerprint

        Returns:
            Dict with rate limit info (limit, remaining, reset_at)

        Raises:
            RateLimitExceeded: If rate limit is exceeded
        """
        allowed, current_count, remaining = await self.check_rate_limit(
            request, fingerprint
        )

        if not allowed:
            ttl = await self.get_ttl(request, fingerprint)
            raise RateLimitExceeded(
                retry_after=ttl,
                limit=self.limit,
                window="24h",
            )

        return {
            "limit": self.limit,
            "remaining": remaining,
            "current": current_count,
        }


async def get_rate_limiter(redis: Optional[Redis] = None) -> AnonymousRateLimiter:
    """Factory function to create rate limiter.

    Args:
        redis: Optional Redis client (will be injected by FastAPI dependency)

    Returns:
        Configured AnonymousRateLimiter instance
    """
    return AnonymousRateLimiter(redis_client=redis)


async def check_anonymous_rate_limit(
    request: Request,
    redis: Optional[Redis] = None,
) -> dict:
    """Dependency function to check rate limit for anonymous users.

    This function can be used as a FastAPI dependency in routes that
    should be rate-limited for anonymous users.

    Usage:
        @router.post("/generate")
        async def generate_map(
            ...,
            rate_limit: dict = Depends(check_anonymous_rate_limit),
        ):
            ...

    Args:
        request: FastAPI request object
        redis: Optional Redis client

    Returns:
        Dict with rate limit info

    Raises:
        RateLimitExceeded: If rate limit is exceeded
    """
    limiter = await get_rate_limiter(redis)
    return await limiter.enforce_rate_limit(request)
