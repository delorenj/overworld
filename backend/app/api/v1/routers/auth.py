"""API router for authentication endpoints.

Provides endpoints for:
- User registration
- User login
- Token refresh
- Logout
- Get current user
- OAuth2 login (Google, GitHub)
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_user,
    get_db,
    get_token_from_header,
)
from app.models.user import User
from app.schemas.auth import (
    AuthMessageResponse,
    OAuthLoginResponse,
    TokenRefreshRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.services.auth_service import (
    InvalidCredentialsError,
    InvalidTokenError,
    OAuthAccountLinkError,
    TokenRevokedError,
    UserAlreadyExistsError,
    get_auth_service,
)
from app.services.oauth import (
    OAuthConfigurationError,
    OAuthTokenError,
    OAuthUserInfoError,
    generate_oauth_state,
)
from app.services.oauth.github import get_github_oauth_provider
from app.services.oauth.google import get_google_oauth_provider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Create a new user account with email and password. Returns JWT tokens.",
)
async def register(
    request: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Register a new user with email and password.

    Creates a new user account and returns access and refresh tokens.
    The user is automatically logged in after registration.

    Args:
        request: Registration data (email, password)
        db: Database session

    Returns:
        TokenResponse: Access and refresh tokens

    Raises:
        HTTPException: 400 if email is already registered
        HTTPException: 422 if validation fails
    """
    auth_service = get_auth_service(db)

    try:
        # Register the user
        user = await auth_service.register_user(
            email=request.email,
            password=request.password,
        )

        # Create tokens for immediate login
        access_token, refresh_token, expires_in = await auth_service.create_tokens(user)

        logger.info(f"User registered and logged in: {user.email}")

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=expires_in,
        )

    except UserAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="User login",
    description="Authenticate with email and password. Returns JWT tokens.",
)
async def login(
    request: UserLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Authenticate a user with email and password.

    Validates credentials and returns access and refresh tokens.

    Args:
        request: Login credentials (email, password)
        db: Database session

    Returns:
        TokenResponse: Access and refresh tokens

    Raises:
        HTTPException: 401 if credentials are invalid
    """
    auth_service = get_auth_service(db)

    try:
        # Authenticate the user
        user = await auth_service.authenticate_user(
            email=request.email,
            password=request.password,
        )

        # Create tokens
        access_token, refresh_token, expires_in = await auth_service.create_tokens(user)

        logger.info(f"User logged in: {user.email}")

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=expires_in,
        )

    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    description="Exchange a refresh token for new access and refresh tokens.",
)
async def refresh_token(
    request: TokenRefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Exchange a refresh token for new tokens.

    Implements token rotation: the old refresh token is invalidated
    and a new one is issued along with a new access token.

    Args:
        request: Refresh token request
        db: Database session

    Returns:
        TokenResponse: New access and refresh tokens

    Raises:
        HTTPException: 401 if refresh token is invalid or revoked
    """
    auth_service = get_auth_service(db)

    try:
        # Refresh tokens
        access_token, new_refresh_token, expires_in = await auth_service.refresh_access_token(
            refresh_token=request.refresh_token,
        )

        logger.info("Tokens refreshed successfully")

        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=expires_in,
        )

    except TokenRevokedError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post(
    "/logout",
    response_model=AuthMessageResponse,
    summary="User logout",
    description="Invalidate the current access token and optional refresh token.",
)
async def logout(
    refresh_token: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    access_token: Optional[str] = Depends(get_token_from_header),
) -> AuthMessageResponse:
    """
    Logout the current user by invalidating their tokens.

    Blacklists the current access token and optionally the refresh token.
    The tokens will no longer be valid for authentication.

    Args:
        refresh_token: Optional refresh token to also invalidate
        db: Database session
        current_user: Currently authenticated user
        access_token: Current access token from header

    Returns:
        AuthMessageResponse: Confirmation message

    Raises:
        HTTPException: 401 if not authenticated
    """
    auth_service = get_auth_service(db)

    if access_token:
        await auth_service.logout(
            access_token=access_token,
            refresh_token=refresh_token,
        )

    logger.info(f"User logged out: {current_user.email}")

    return AuthMessageResponse(message="Successfully logged out")


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Get the profile of the currently authenticated user.",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """
    Get the current user's profile.

    Returns information about the authenticated user.

    Args:
        current_user: Currently authenticated user

    Returns:
        UserResponse: User profile information

    Raises:
        HTTPException: 401 if not authenticated
    """
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        is_verified=current_user.is_verified,
        is_premium=current_user.is_premium,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
    )


# =============================================================================
# OAuth2 - Google
# =============================================================================


@router.get(
    "/google/login",
    response_model=OAuthLoginResponse,
    summary="Initiate Google OAuth login",
    description="Get the Google OAuth authorization URL to redirect the user to.",
)
async def google_login() -> OAuthLoginResponse:
    """
    Initiate Google OAuth2 login flow.

    Returns the authorization URL that the frontend should redirect the user to.
    Also returns a state parameter that should be stored (e.g., in session/cookie)
    and validated during the callback.

    Returns:
        OAuthLoginResponse: Authorization URL and state parameter

    Raises:
        HTTPException: 501 if Google OAuth is not configured
    """
    try:
        provider = get_google_oauth_provider()
        state = generate_oauth_state()
        auth_url = provider.get_authorization_url(state)

        logger.info("Generated Google OAuth login URL")

        return OAuthLoginResponse(
            authorization_url=auth_url,
            state=state,
        )

    except OAuthConfigurationError as e:
        logger.error(f"Google OAuth not configured: {e}")
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth is not configured",
        )


@router.get(
    "/google/callback",
    response_model=TokenResponse,
    summary="Google OAuth callback",
    description="Handle the callback from Google OAuth and return JWT tokens.",
)
async def google_callback(
    code: str = Query(..., description="Authorization code from Google"),
    state: str = Query(..., description="State parameter for CSRF validation"),
    error: Optional[str] = Query(None, description="Error code from Google"),
    error_description: Optional[str] = Query(None, description="Error description"),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Handle Google OAuth2 callback.

    Exchanges the authorization code for tokens, fetches user info,
    and creates/links the user account. Returns JWT tokens for the application.

    Note: The frontend should validate the state parameter matches
    what was returned from the login endpoint.

    Args:
        code: Authorization code from Google
        state: State parameter (frontend should validate this)
        error: Optional error code from Google
        error_description: Optional error description
        db: Database session

    Returns:
        TokenResponse: JWT access and refresh tokens

    Raises:
        HTTPException: 400 if OAuth error or authentication fails
        HTTPException: 501 if Google OAuth is not configured
    """
    # Check for OAuth error
    if error:
        logger.warning(f"Google OAuth error: {error} - {error_description}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_description or error,
        )

    try:
        # Get provider and authenticate
        provider = get_google_oauth_provider()
        user_info = await provider.authenticate(code)

        # Get or create user
        auth_service = get_auth_service(db)
        user = await auth_service.authenticate_oauth_user(user_info)

        # Create JWT tokens
        access_token, refresh_token, expires_in = await auth_service.create_tokens(user)

        logger.info(f"Google OAuth login successful for: {user.email}")

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=expires_in,
        )

    except OAuthConfigurationError as e:
        logger.error(f"Google OAuth not configured: {e}")
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth is not configured",
        )
    except OAuthTokenError as e:
        logger.error(f"Google token exchange failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to authenticate with Google: {e}",
        )
    except OAuthUserInfoError as e:
        logger.error(f"Google user info fetch failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to get user information from Google: {e}",
        )
    except OAuthAccountLinkError as e:
        logger.warning(f"OAuth account link error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# =============================================================================
# OAuth2 - GitHub
# =============================================================================


@router.get(
    "/github/login",
    response_model=OAuthLoginResponse,
    summary="Initiate GitHub OAuth login",
    description="Get the GitHub OAuth authorization URL to redirect the user to.",
)
async def github_login() -> OAuthLoginResponse:
    """
    Initiate GitHub OAuth2 login flow.

    Returns the authorization URL that the frontend should redirect the user to.
    Also returns a state parameter that should be stored (e.g., in session/cookie)
    and validated during the callback.

    Returns:
        OAuthLoginResponse: Authorization URL and state parameter

    Raises:
        HTTPException: 501 if GitHub OAuth is not configured
    """
    try:
        provider = get_github_oauth_provider()
        state = generate_oauth_state()
        auth_url = provider.get_authorization_url(state)

        logger.info("Generated GitHub OAuth login URL")

        return OAuthLoginResponse(
            authorization_url=auth_url,
            state=state,
        )

    except OAuthConfigurationError as e:
        logger.error(f"GitHub OAuth not configured: {e}")
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="GitHub OAuth is not configured",
        )


@router.get(
    "/github/callback",
    response_model=TokenResponse,
    summary="GitHub OAuth callback",
    description="Handle the callback from GitHub OAuth and return JWT tokens.",
)
async def github_callback(
    code: str = Query(..., description="Authorization code from GitHub"),
    state: str = Query(..., description="State parameter for CSRF validation"),
    error: Optional[str] = Query(None, description="Error code from GitHub"),
    error_description: Optional[str] = Query(None, description="Error description"),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Handle GitHub OAuth2 callback.

    Exchanges the authorization code for tokens, fetches user info,
    and creates/links the user account. Returns JWT tokens for the application.

    Note: The frontend should validate the state parameter matches
    what was returned from the login endpoint.

    Args:
        code: Authorization code from GitHub
        state: State parameter (frontend should validate this)
        error: Optional error code from GitHub
        error_description: Optional error description
        db: Database session

    Returns:
        TokenResponse: JWT access and refresh tokens

    Raises:
        HTTPException: 400 if OAuth error or authentication fails
        HTTPException: 501 if GitHub OAuth is not configured
    """
    # Check for OAuth error
    if error:
        logger.warning(f"GitHub OAuth error: {error} - {error_description}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_description or error,
        )

    try:
        # Get provider and authenticate
        provider = get_github_oauth_provider()
        user_info = await provider.authenticate(code)

        # Get or create user
        auth_service = get_auth_service(db)
        user = await auth_service.authenticate_oauth_user(user_info)

        # Create JWT tokens
        access_token, refresh_token, expires_in = await auth_service.create_tokens(user)

        logger.info(f"GitHub OAuth login successful for: {user.email}")

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=expires_in,
        )

    except OAuthConfigurationError as e:
        logger.error(f"GitHub OAuth not configured: {e}")
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="GitHub OAuth is not configured",
        )
    except OAuthTokenError as e:
        logger.error(f"GitHub token exchange failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to authenticate with GitHub: {e}",
        )
    except OAuthUserInfoError as e:
        logger.error(f"GitHub user info fetch failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to get user information from GitHub: {e}",
        )
    except OAuthAccountLinkError as e:
        logger.warning(f"OAuth account link error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
