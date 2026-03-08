"""API dependencies for FastAPI route handlers.

This module provides dependency injection functions for:
- Database sessions
- Redis connections
- Authentication (JWT-based)
- Job queue service
"""

from typing import AsyncGenerator, Optional

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from app.core.config import settings
from app.core.database import get_db as get_db_session
from app.core.redis import get_redis as get_redis_client
from app.models.user import User
from app.schemas.generation_job import GenerationJobCreate
from app.services.job_queue import JobQueueService
from app.services.token_service import (
    ANONYMOUS_OPERATION_EXPORT,
    EXPORT_TOKEN_COST,
    AnonymousFreeTierExceededError,
    TokenService,
    get_token_service,
)
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


def get_client_ip(request: Request) -> str:
    """Extract best-effort client IP (proxy-aware)."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def build_anonymous_client_hash(request: Request, session_id: Optional[str] = None) -> str:
    """Build anonymous client hash from IP + session id."""
    cookie_session = request.cookies.get("overworld_session")
    return TokenService.build_anonymous_client_hash(
        ip_address=get_client_ip(request),
        session_id=session_id or cookie_session,
    )


async def require_generation_tokens(
    job_data: GenerationJobCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Dependency: ensure authenticated user can afford generation request."""
    token_service = get_token_service(db)
    estimate = await token_service.estimate_job_cost(document_id=job_data.document_id)
    required = estimate["estimated_cost"]
    available = await token_service.get_balance(current_user.id)

    if available < required:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "message": "Insufficient token balance",
                "required": required,
                "available": available,
                "shortfall": required - available,
            },
        )

    return {"required": required, "available": available}


async def require_export_tokens(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Dependency: ensure authenticated user can afford an export."""
    token_service = get_token_service(db)
    available = await token_service.get_balance(current_user.id)

    if available < EXPORT_TOKEN_COST:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "message": "Insufficient token balance",
                "required": EXPORT_TOKEN_COST,
                "available": available,
                "shortfall": EXPORT_TOKEN_COST - available,
            },
        )

    return {"required": EXPORT_TOKEN_COST, "available": available}


async def consume_anonymous_export_quota(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_session_id: Optional[str] = Header(default=None, alias="X-Session-ID"),
) -> dict:
    """Consume one anonymous free-tier export unit based on session/IP fingerprint."""
    token_service = get_token_service(db)
    client_hash = build_anonymous_client_hash(request, x_session_id)

    try:
        return await token_service.consume_anonymous_operation(
            client_id_hash=client_hash,
            operation=ANONYMOUS_OPERATION_EXPORT,
            amount=1,
        )
    except AnonymousFreeTierExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "message": "Anonymous free tier exhausted",
                "limit": e.limit,
                "used": e.used,
                "remaining": e.remaining,
            },
        )


async def require_admin_api_key(
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
) -> None:
    """Dependency: verify admin key for privileged token operations."""
    if not settings.TOKEN_ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin token crediting is not configured",
        )

    if not x_admin_key or x_admin_key != settings.TOKEN_ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin key",
        )


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
