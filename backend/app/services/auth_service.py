"""Authentication service for user registration, login, and token management.

This module provides:
- Password hashing with bcrypt
- JWT token generation and validation (access + refresh tokens)
- User registration with email validation
- Token refresh logic
- Token blacklisting for logout
- OAuth2 authentication and account linking
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.schemas.auth import TokenPayload
from app.services.oauth import OAuthProvider, OAuthUserInfo

logger = logging.getLogger(__name__)

# Password hashing context using bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# In-memory token blacklist (for production, use Redis)
# This set stores JTIs (JWT IDs) of revoked tokens
_token_blacklist: set[str] = set()


class AuthServiceError(Exception):
    """Base exception for authentication service errors."""

    pass


class InvalidCredentialsError(AuthServiceError):
    """Raised when login credentials are invalid."""

    pass


class UserAlreadyExistsError(AuthServiceError):
    """Raised when attempting to register with an existing email."""

    pass


class InvalidTokenError(AuthServiceError):
    """Raised when a token is invalid or expired."""

    pass


class TokenRevokedError(AuthServiceError):
    """Raised when a revoked token is used."""

    pass


class OAuthAccountLinkError(AuthServiceError):
    """Raised when OAuth account linking fails."""

    pass


class AuthService:
    """Service class for authentication operations."""

    def __init__(self, db: AsyncSession):
        """Initialize auth service with database session.

        Args:
            db: Async SQLAlchemy session
        """
        self.db = db

    # -------------------------------------------------------------------------
    # Password Hashing
    # -------------------------------------------------------------------------

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt.

        Args:
            password: Plain text password

        Returns:
            Hashed password string
        """
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash.

        Args:
            plain_password: Plain text password to verify
            hashed_password: Bcrypt hash to verify against

        Returns:
            True if password matches, False otherwise
        """
        return pwd_context.verify(plain_password, hashed_password)

    # -------------------------------------------------------------------------
    # JWT Token Management
    # -------------------------------------------------------------------------

    @staticmethod
    def create_access_token(user_id: int) -> tuple[str, int]:
        """Create a JWT access token for a user.

        Args:
            user_id: User's database ID

        Returns:
            Tuple of (token string, expiration timestamp in seconds)
        """
        now = datetime.now(UTC)
        expires_delta = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        expire = now + expires_delta

        payload = {
            "sub": str(user_id),
            "type": "access",
            "exp": int(expire.timestamp()),
            "iat": int(now.timestamp()),
        }

        token = jwt.encode(
            payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )

        return token, settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60

    @staticmethod
    def create_refresh_token(user_id: int) -> str:
        """Create a JWT refresh token for a user.

        Args:
            user_id: User's database ID

        Returns:
            Refresh token string
        """
        now = datetime.now(UTC)
        expires_delta = timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
        expire = now + expires_delta

        payload = {
            "sub": str(user_id),
            "type": "refresh",
            "exp": int(expire.timestamp()),
            "iat": int(now.timestamp()),
        }

        return jwt.encode(
            payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )

    @staticmethod
    def decode_token(token: str) -> TokenPayload:
        """Decode and validate a JWT token.

        Args:
            token: JWT token string

        Returns:
            TokenPayload with decoded claims

        Raises:
            InvalidTokenError: If token is invalid or expired
        """
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )
            return TokenPayload(
                sub=payload["sub"],
                type=payload["type"],
                exp=payload["exp"],
                iat=payload["iat"],
            )
        except JWTError as e:
            logger.warning(f"Token decode error: {e}")
            raise InvalidTokenError("Invalid or expired token")

    @staticmethod
    def is_token_blacklisted(token: str) -> bool:
        """Check if a token has been revoked.

        Args:
            token: JWT token string

        Returns:
            True if token is blacklisted, False otherwise
        """
        return token in _token_blacklist

    @staticmethod
    def blacklist_token(token: str) -> None:
        """Add a token to the blacklist.

        Args:
            token: JWT token string to revoke
        """
        _token_blacklist.add(token)
        logger.info(f"Token blacklisted (total blacklisted: {len(_token_blacklist)})")

    # -------------------------------------------------------------------------
    # User Operations
    # -------------------------------------------------------------------------

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get a user by email address.

        Args:
            email: User's email address

        Returns:
            User if found, None otherwise
        """
        query = select(User).where(User.email == email.lower())
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get a user by ID.

        Args:
            user_id: User's database ID

        Returns:
            User if found, None otherwise
        """
        query = select(User).where(User.id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def register_user(self, email: str, password: str) -> User:
        """Register a new user.

        Args:
            email: User's email address
            password: Plain text password

        Returns:
            Newly created User

        Raises:
            UserAlreadyExistsError: If email is already registered
        """
        # Normalize email to lowercase
        email = email.lower()

        # Check if user already exists
        existing_user = await self.get_user_by_email(email)
        if existing_user:
            raise UserAlreadyExistsError(f"User with email {email} already exists")

        # Hash password and create user
        password_hash = self.hash_password(password)
        user = User(
            email=email,
            password_hash=password_hash,
            is_verified=False,  # Will be set to True after email verification
        )

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        logger.info(f"New user registered: {email} (ID: {user.id})")
        return user

    async def authenticate_user(self, email: str, password: str) -> User:
        """Authenticate a user with email and password.

        Args:
            email: User's email address
            password: Plain text password

        Returns:
            Authenticated User

        Raises:
            InvalidCredentialsError: If credentials are invalid
        """
        user = await self.get_user_by_email(email.lower())

        if not user:
            logger.warning(f"Login attempt for non-existent user: {email}")
            raise InvalidCredentialsError("Invalid email or password")

        if not user.password_hash:
            # User registered via OAuth, cannot login with password
            logger.warning(f"Password login attempt for OAuth user: {email}")
            raise InvalidCredentialsError("Invalid email or password")

        if not self.verify_password(password, user.password_hash):
            logger.warning(f"Invalid password for user: {email}")
            raise InvalidCredentialsError("Invalid email or password")

        logger.info(f"User authenticated: {email}")
        return user

    async def create_tokens(self, user: User) -> tuple[str, str, int]:
        """Create access and refresh tokens for a user.

        Args:
            user: User to create tokens for

        Returns:
            Tuple of (access_token, refresh_token, expires_in_seconds)
        """
        access_token, expires_in = self.create_access_token(user.id)
        refresh_token = self.create_refresh_token(user.id)

        return access_token, refresh_token, expires_in

    async def refresh_access_token(self, refresh_token: str) -> tuple[str, str, int]:
        """Exchange a refresh token for new access and refresh tokens.

        Args:
            refresh_token: Valid refresh token

        Returns:
            Tuple of (new_access_token, new_refresh_token, expires_in_seconds)

        Raises:
            InvalidTokenError: If refresh token is invalid
            TokenRevokedError: If refresh token has been revoked
        """
        # Check if token is blacklisted
        if self.is_token_blacklisted(refresh_token):
            raise TokenRevokedError("Refresh token has been revoked")

        # Decode and validate token
        payload = self.decode_token(refresh_token)

        if payload.type != "refresh":
            raise InvalidTokenError("Invalid token type")

        # Get user
        user = await self.get_user_by_id(int(payload.sub))
        if not user:
            raise InvalidTokenError("User not found")

        # Blacklist old refresh token (rotation)
        self.blacklist_token(refresh_token)

        # Create new tokens
        return await self.create_tokens(user)

    async def logout(self, access_token: str, refresh_token: Optional[str] = None) -> None:
        """Logout a user by blacklisting their tokens.

        Args:
            access_token: Current access token to revoke
            refresh_token: Optional refresh token to also revoke
        """
        self.blacklist_token(access_token)

        if refresh_token:
            self.blacklist_token(refresh_token)

        logger.info("User logged out, tokens blacklisted")

    async def validate_access_token(self, token: str) -> User:
        """Validate an access token and return the associated user.

        Args:
            token: JWT access token

        Returns:
            User associated with the token

        Raises:
            InvalidTokenError: If token is invalid
            TokenRevokedError: If token has been revoked
        """
        # Check if token is blacklisted
        if self.is_token_blacklisted(token):
            raise TokenRevokedError("Token has been revoked")

        # Decode and validate token
        payload = self.decode_token(token)

        if payload.type != "access":
            raise InvalidTokenError("Invalid token type")

        # Get user
        user = await self.get_user_by_id(int(payload.sub))
        if not user:
            raise InvalidTokenError("User not found")

        return user

    # -------------------------------------------------------------------------
    # OAuth2 Authentication
    # -------------------------------------------------------------------------

    async def get_user_by_oauth(
        self, provider: OAuthProvider, provider_user_id: str
    ) -> Optional[User]:
        """Get a user by OAuth provider and provider user ID.

        Args:
            provider: OAuth provider (google, github)
            provider_user_id: User's ID from the OAuth provider

        Returns:
            User if found, None otherwise
        """
        query = select(User).where(
            User.oauth_provider == provider.value,
            User.oauth_id == provider_user_id,
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def authenticate_oauth_user(self, user_info: OAuthUserInfo) -> User:
        """Authenticate or create a user from OAuth provider info.

        This method handles three scenarios:
        1. User exists with matching OAuth provider/ID -> return existing user
        2. User exists with same email -> link OAuth to existing account
        3. No existing user -> create new account

        Args:
            user_info: Normalized user info from OAuth provider

        Returns:
            Authenticated User (existing or newly created)

        Raises:
            OAuthAccountLinkError: If account linking fails
        """
        # Check if user already exists with this OAuth provider
        existing_oauth_user = await self.get_user_by_oauth(
            user_info.provider, user_info.provider_user_id
        )

        if existing_oauth_user:
            logger.info(
                f"OAuth login for existing user: {existing_oauth_user.email} "
                f"via {user_info.provider.value}"
            )
            return existing_oauth_user

        # Check if user exists with same email
        existing_email_user = await self.get_user_by_email(user_info.email)

        if existing_email_user:
            # Link OAuth to existing account
            return await self._link_oauth_to_user(existing_email_user, user_info)

        # Create new user
        return await self._create_oauth_user(user_info)

    async def _link_oauth_to_user(
        self, user: User, user_info: OAuthUserInfo
    ) -> User:
        """Link OAuth provider to an existing user account.

        This allows users who registered with email/password to later
        sign in with OAuth providers.

        Args:
            user: Existing user to link OAuth to
            user_info: OAuth user info to link

        Returns:
            Updated user with OAuth linked

        Raises:
            OAuthAccountLinkError: If user already has a different OAuth linked
        """
        # Check if user already has OAuth linked
        if user.oauth_provider and user.oauth_id:
            # Check if it's the same provider but different ID
            if user.oauth_provider == user_info.provider.value:
                if user.oauth_id != user_info.provider_user_id:
                    logger.warning(
                        f"OAuth ID mismatch for user {user.email}: "
                        f"existing={user.oauth_id}, new={user_info.provider_user_id}"
                    )
                    raise OAuthAccountLinkError(
                        f"This email is already linked to a different {user_info.provider.value} account"
                    )
            else:
                # Different provider - for MVP, we only support one OAuth per user
                # Future enhancement: support multiple OAuth providers per user
                logger.warning(
                    f"User {user.email} already has OAuth linked to {user.oauth_provider}, "
                    f"cannot link to {user_info.provider.value}"
                )
                raise OAuthAccountLinkError(
                    f"This email is already linked to {user.oauth_provider}. "
                    f"Please sign in with {user.oauth_provider} instead."
                )

        # Link OAuth to user
        user.oauth_provider = user_info.provider.value
        user.oauth_id = user_info.provider_user_id

        # If OAuth email is verified and user isn't verified, verify them
        if user_info.email_verified and not user.is_verified:
            user.is_verified = True
            logger.info(f"User {user.email} verified through OAuth")

        await self.db.commit()
        await self.db.refresh(user)

        logger.info(
            f"Linked {user_info.provider.value} OAuth to existing user: {user.email}"
        )
        return user

    async def _create_oauth_user(self, user_info: OAuthUserInfo) -> User:
        """Create a new user from OAuth provider info.

        Args:
            user_info: OAuth user info

        Returns:
            Newly created User
        """
        user = User(
            email=user_info.email,
            password_hash=None,  # OAuth users don't have passwords
            oauth_provider=user_info.provider.value,
            oauth_id=user_info.provider_user_id,
            is_verified=user_info.email_verified,  # Trust OAuth provider verification
        )

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        logger.info(
            f"New user registered via {user_info.provider.value}: "
            f"{user.email} (ID: {user.id})"
        )
        return user


# Utility function to get auth service instance
def get_auth_service(db: AsyncSession) -> AuthService:
    """Factory function to create AuthService instance.

    Args:
        db: Async SQLAlchemy session

    Returns:
        AuthService instance
    """
    return AuthService(db)
