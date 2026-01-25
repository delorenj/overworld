"""API dependencies for FastAPI route handlers.

This module provides dependency injection functions for:
- Database sessions
- Redis connections
- Authentication (JWT-based)
- Job queue service
"""

from typing import AsyncGenerator, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from app.core.database import get_db as get_db_session
from app.core.redis import get_redis as get_redis_client
from app.core.arq_config import get_arq_pool
from app.models.user import User
from app.services.job_queue import JobQueueService
from app.services.auth_service import (
    AuthService,
    InvalidTokenError,
    TokenRevokedError,
    get_auth_service,
)


# HTTP Bearer token scheme for JWT authentication
security = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session.

    Yields:
        AsyncSession for database operations
    """
    async for session in get_db_session():
        yield session


async def get_redis() -> redis.Redis:
    """Dependency to get Redis client.

    Returns:
        Redis client instance
    """
    return await get_redis_client()


async def get_rabbitmq():
    """Legacy dependency for RabbitMQ (deprecated, use ARQ).

    This is kept for backward compatibility with existing code.
    New code should use the job queue service instead.

    Returns:
        RabbitMQ connection (placeholder)
    """
    # This will be removed once all code migrates to ARQ
    from app.core.queue import get_rabbitmq as legacy_get_rabbitmq
    return await legacy_get_rabbitmq()


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> User:
    """Dependency to get the current authenticated user from JWT token.

    Extracts the JWT token from the Authorization header, validates it,
    and returns the associated user.

    Args:
        db: Database session
        credentials: HTTP Bearer credentials containing the JWT token

    Returns:
        User: The authenticated user

    Raises:
        HTTPException: 401 if token is missing, invalid, or expired
    """
    # Check if credentials were provided
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    auth_service = get_auth_service(db)

    try:
        user = await auth_service.validate_access_token(token)
        return user
    except TokenRevokedError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_optional_user(
    db: AsyncSession = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[User]:
    """Dependency to get the current user if authenticated, or None.

    This is useful for endpoints that work with or without authentication.

    Args:
        db: Database session
        credentials: Optional HTTP Bearer credentials

    Returns:
        User if authenticated, None otherwise
    """
    if not credentials:
        return None

    try:
        token = credentials.credentials
        auth_service = get_auth_service(db)
        return await auth_service.validate_access_token(token)
    except (TokenRevokedError, InvalidTokenError):
        return None


async def get_job_queue_service(
    db: AsyncSession = Depends(get_db),
) -> JobQueueService:
    """Dependency to get JobQueueService instance.

    Args:
        db: Database session from dependency

    Returns:
        Configured JobQueueService
    """
    return JobQueueService(db)


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Dependency to verify user is verified/active.

    Args:
        current_user: User from get_current_user

    Returns:
        User if verified

    Raises:
        HTTPException: If user is not verified
    """
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account not verified",
        )
    return current_user


def get_token_from_header(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[str]:
    """Extract the raw token string from Authorization header.

    Useful for logout and token refresh operations.

    Args:
        credentials: HTTP Bearer credentials

    Returns:
        Token string if present, None otherwise
    """
    if credentials:
        return credentials.credentials
    return None
