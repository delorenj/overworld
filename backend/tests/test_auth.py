"""Comprehensive tests for authentication system.

Tests cover:
- User registration
- User login
- Token generation and validation
- Token refresh
- Logout and token revocation
- Password hashing
- Protected endpoint access
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models import User
from app.services.auth_service import (
    AuthService,
    InvalidCredentialsError,
    InvalidTokenError,
    TokenRevokedError,
    UserAlreadyExistsError,
    get_auth_service,
    pwd_context,
    _token_blacklist,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def clear_token_blacklist():
    """Clear the token blacklist before each test."""
    _token_blacklist.clear()
    yield
    _token_blacklist.clear()


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = AsyncMock(spec=AsyncSession)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock()
    return db


@pytest.fixture
def auth_service(mock_db):
    """Provide an AuthService instance with mock db."""
    return AuthService(mock_db)


@pytest.fixture
def test_user():
    """Create a test user with a known password."""
    password = "TestPassword123"
    hashed_password = pwd_context.hash(password)

    user = User(
        id=1,
        email="test@example.com",
        password_hash=hashed_password,
        is_verified=True,
        is_premium=False,
        created_at=datetime.now(timezone.utc),
    )

    # Attach plain password for testing
    user._test_password = password
    return user


@pytest.fixture
def valid_registration_data():
    """Provide valid registration data."""
    return {
        "email": "newuser@example.com",
        "password": "ValidPassword123",
    }


@pytest.fixture
def valid_login_data():
    """Provide valid login data (matching test_user)."""
    return {
        "email": "test@example.com",
        "password": "TestPassword123",
    }


# =============================================================================
# Unit Tests - Password Hashing
# =============================================================================


class TestPasswordHashing:
    """Test password hashing functionality."""

    def test_hash_password(self):
        """Test that password hashing produces a valid hash."""
        password = "TestPassword123"
        hashed = AuthService.hash_password(password)

        assert hashed != password
        assert hashed.startswith("$2b$")  # bcrypt prefix
        assert len(hashed) == 60  # bcrypt hash length

    def test_verify_password_correct(self):
        """Test that correct password verifies successfully."""
        password = "TestPassword123"
        hashed = AuthService.hash_password(password)

        assert AuthService.verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test that incorrect password fails verification."""
        password = "TestPassword123"
        wrong_password = "WrongPassword456"
        hashed = AuthService.hash_password(password)

        assert AuthService.verify_password(wrong_password, hashed) is False

    def test_hash_uniqueness(self):
        """Test that same password produces different hashes (salting)."""
        password = "TestPassword123"
        hash1 = AuthService.hash_password(password)
        hash2 = AuthService.hash_password(password)

        assert hash1 != hash2
        # Both should still verify correctly
        assert AuthService.verify_password(password, hash1) is True
        assert AuthService.verify_password(password, hash2) is True


# =============================================================================
# Unit Tests - JWT Token Management
# =============================================================================


class TestJWTTokens:
    """Test JWT token generation and validation."""

    def test_create_access_token(self):
        """Test access token creation."""
        user_id = 123
        token, expires_in = AuthService.create_access_token(user_id)

        assert isinstance(token, str)
        assert len(token) > 0
        assert expires_in > 0

        # Decode and verify payload
        payload = AuthService.decode_token(token)
        assert payload.sub == str(user_id)
        assert payload.type == "access"

    def test_create_refresh_token(self):
        """Test refresh token creation."""
        user_id = 123
        token = AuthService.create_refresh_token(user_id)

        assert isinstance(token, str)
        assert len(token) > 0

        # Decode and verify payload
        payload = AuthService.decode_token(token)
        assert payload.sub == str(user_id)
        assert payload.type == "refresh"

    def test_decode_invalid_token(self):
        """Test that invalid token raises error."""
        with pytest.raises(InvalidTokenError):
            AuthService.decode_token("invalid.token.here")

    def test_decode_malformed_token(self):
        """Test that malformed token raises error."""
        with pytest.raises(InvalidTokenError):
            AuthService.decode_token("not_a_jwt_at_all")

    def test_token_blacklisting(self):
        """Test token blacklisting functionality."""
        token = "test_token_to_blacklist"

        assert AuthService.is_token_blacklisted(token) is False
        AuthService.blacklist_token(token)
        assert AuthService.is_token_blacklisted(token) is True


# =============================================================================
# Unit Tests - Auth Service with Mocked Database
# =============================================================================


class TestAuthServiceWithMocks:
    """Unit tests for AuthService with mocked database."""

    @pytest.mark.asyncio
    async def test_register_user_success(self, mock_db, auth_service):
        """Test successful user registration."""
        email = "newuser@example.com"
        password = "ValidPassword123"

        # Mock that no existing user is found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        # Mock refresh to set user id
        async def set_user_id(user):
            user.id = 1

        mock_db.refresh = AsyncMock(side_effect=set_user_id)

        user = await auth_service.register_user(email, password)

        assert user.email == email.lower()
        assert user.password_hash is not None
        assert user.password_hash != password
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_user_duplicate_email(self, mock_db, auth_service, test_user):
        """Test registration with existing email raises error."""
        # Mock that user is found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = test_user
        mock_db.execute.return_value = mock_result

        with pytest.raises(UserAlreadyExistsError):
            await auth_service.register_user(
                email=test_user.email,
                password="AnotherPassword123",
            )

    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, mock_db, auth_service, test_user):
        """Test successful user authentication."""
        # Mock that user is found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = test_user
        mock_db.execute.return_value = mock_result

        user = await auth_service.authenticate_user(
            email=test_user.email,
            password=test_user._test_password,
        )

        assert user.id == test_user.id
        assert user.email == test_user.email

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(self, mock_db, auth_service, test_user):
        """Test authentication with wrong password."""
        # Mock that user is found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = test_user
        mock_db.execute.return_value = mock_result

        with pytest.raises(InvalidCredentialsError):
            await auth_service.authenticate_user(
                email=test_user.email,
                password="WrongPassword123",
            )

    @pytest.mark.asyncio
    async def test_authenticate_user_nonexistent(self, mock_db, auth_service):
        """Test authentication with non-existent email."""
        # Mock that no user is found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(InvalidCredentialsError):
            await auth_service.authenticate_user(
                email="nonexistent@example.com",
                password="SomePassword123",
            )

    @pytest.mark.asyncio
    async def test_create_tokens(self, auth_service, test_user):
        """Test token creation for user."""
        access_token, refresh_token, expires_in = await auth_service.create_tokens(test_user)

        assert access_token is not None
        assert refresh_token is not None
        assert expires_in > 0

        # Verify access token
        access_payload = AuthService.decode_token(access_token)
        assert access_payload.sub == str(test_user.id)
        assert access_payload.type == "access"

        # Verify refresh token
        refresh_payload = AuthService.decode_token(refresh_token)
        assert refresh_payload.sub == str(test_user.id)
        assert refresh_payload.type == "refresh"

    @pytest.mark.asyncio
    async def test_refresh_access_token_success(self, mock_db, auth_service, test_user):
        """Test successful token refresh."""
        # Create initial tokens
        _, refresh_token, _ = await auth_service.create_tokens(test_user)

        # Mock that user is found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = test_user
        mock_db.execute.return_value = mock_result

        # Refresh tokens
        new_access, new_refresh, expires_in = await auth_service.refresh_access_token(refresh_token)

        assert new_access is not None
        assert new_refresh is not None
        # Note: new_refresh may equal refresh_token if created at same timestamp
        # The important thing is that old token is blacklisted (rotation)

        # Old refresh token should be blacklisted
        assert AuthService.is_token_blacklisted(refresh_token) is True

    @pytest.mark.asyncio
    async def test_refresh_with_access_token_fails(self, mock_db, auth_service, test_user):
        """Test that using access token for refresh fails."""
        access_token, _, _ = await auth_service.create_tokens(test_user)

        with pytest.raises(InvalidTokenError):
            await auth_service.refresh_access_token(access_token)

    @pytest.mark.asyncio
    async def test_validate_access_token(self, mock_db, auth_service, test_user):
        """Test access token validation."""
        access_token, _, _ = await auth_service.create_tokens(test_user)

        # Mock that user is found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = test_user
        mock_db.execute.return_value = mock_result

        user = await auth_service.validate_access_token(access_token)

        assert user.id == test_user.id
        assert user.email == test_user.email

    @pytest.mark.asyncio
    async def test_validate_revoked_token(self, mock_db, auth_service, test_user):
        """Test that revoked token fails validation."""
        access_token, _, _ = await auth_service.create_tokens(test_user)
        AuthService.blacklist_token(access_token)

        with pytest.raises(TokenRevokedError):
            await auth_service.validate_access_token(access_token)


# =============================================================================
# API Endpoint Tests - Registration (mocked)
# =============================================================================


class TestRegisterEndpoint:
    """Test POST /api/v1/auth/register endpoint."""

    @pytest.mark.asyncio
    @patch("app.api.v1.routers.auth.get_auth_service")
    async def test_register_success(self, mock_get_service, valid_registration_data, test_user):
        """Test successful registration."""
        mock_service = AsyncMock()
        mock_service.register_user.return_value = test_user
        mock_service.create_tokens.return_value = ("access_token", "refresh_token", 86400)
        mock_get_service.return_value = mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/register",
                json=valid_registration_data,
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data

    @pytest.mark.asyncio
    @patch("app.api.v1.routers.auth.get_auth_service")
    async def test_register_duplicate_email(self, mock_get_service, valid_registration_data):
        """Test registration with existing email."""
        mock_service = AsyncMock()
        mock_service.register_user.side_effect = UserAlreadyExistsError("User already exists")
        mock_get_service.return_value = mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/register",
                json=valid_registration_data,
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already exists" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_register_invalid_email(self):
        """Test registration with invalid email format."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": "not_an_email",
                    "password": "ValidPassword123",
                },
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_register_weak_password_no_uppercase(self):
        """Test registration with password missing uppercase."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": "test@example.com",
                    "password": "nouppercase123",
                },
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_register_weak_password_no_lowercase(self):
        """Test registration with password missing lowercase."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": "test@example.com",
                    "password": "NOLOWERCASE123",
                },
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_register_weak_password_no_digit(self):
        """Test registration with password missing digit."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": "test@example.com",
                    "password": "NoDigitPassword",
                },
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_register_password_too_short(self):
        """Test registration with password too short."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": "test@example.com",
                    "password": "Short1",  # Less than 8 chars
                },
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# =============================================================================
# API Endpoint Tests - Login (mocked)
# =============================================================================


class TestLoginEndpoint:
    """Test POST /api/v1/auth/login endpoint."""

    @pytest.mark.asyncio
    @patch("app.api.v1.routers.auth.get_auth_service")
    async def test_login_success(self, mock_get_service, valid_login_data, test_user):
        """Test successful login."""
        mock_service = AsyncMock()
        mock_service.authenticate_user.return_value = test_user
        mock_service.create_tokens.return_value = ("access_token", "refresh_token", 86400)
        mock_get_service.return_value = mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/login",
                json=valid_login_data,
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data

    @pytest.mark.asyncio
    @patch("app.api.v1.routers.auth.get_auth_service")
    async def test_login_wrong_password(self, mock_get_service, valid_login_data):
        """Test login with wrong password."""
        mock_service = AsyncMock()
        mock_service.authenticate_user.side_effect = InvalidCredentialsError("Invalid credentials")
        mock_get_service.return_value = mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/login",
                json=valid_login_data,
            )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid email or password" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch("app.api.v1.routers.auth.get_auth_service")
    async def test_login_nonexistent_user(self, mock_get_service):
        """Test login with non-existent email."""
        mock_service = AsyncMock()
        mock_service.authenticate_user.side_effect = InvalidCredentialsError("Invalid credentials")
        mock_get_service.return_value = mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": "nonexistent@example.com",
                    "password": "SomePassword123",
                },
            )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_login_invalid_email_format(self):
        """Test login with invalid email format."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": "not_an_email",
                    "password": "SomePassword123",
                },
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# =============================================================================
# API Endpoint Tests - Token Refresh (mocked)
# =============================================================================


class TestRefreshEndpoint:
    """Test POST /api/v1/auth/refresh endpoint."""

    @pytest.mark.asyncio
    @patch("app.api.v1.routers.auth.get_auth_service")
    async def test_refresh_success(self, mock_get_service):
        """Test successful token refresh."""
        mock_service = AsyncMock()
        mock_service.refresh_access_token.return_value = ("new_access", "new_refresh", 86400)
        mock_get_service.return_value = mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": "valid_refresh_token"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["access_token"] == "new_access"
        assert data["refresh_token"] == "new_refresh"

    @pytest.mark.asyncio
    @patch("app.api.v1.routers.auth.get_auth_service")
    async def test_refresh_invalid_token(self, mock_get_service):
        """Test refresh with invalid token."""
        mock_service = AsyncMock()
        mock_service.refresh_access_token.side_effect = InvalidTokenError("Invalid token")
        mock_get_service.return_value = mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": "invalid.token.here"},
            )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    @patch("app.api.v1.routers.auth.get_auth_service")
    async def test_refresh_revoked_token(self, mock_get_service):
        """Test that revoked refresh token fails."""
        mock_service = AsyncMock()
        mock_service.refresh_access_token.side_effect = TokenRevokedError("Token revoked")
        mock_get_service.return_value = mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": "revoked_token"},
            )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "revoked" in response.json()["detail"]


# =============================================================================
# API Endpoint Tests - Logout (mocked)
# =============================================================================


class TestLogoutEndpoint:
    """Test POST /api/v1/auth/logout endpoint."""

    @pytest.mark.asyncio
    @patch("app.api.deps.get_auth_service")
    async def test_logout_success(self, mock_get_service, test_user):
        """Test successful logout."""
        mock_service = AsyncMock()
        mock_service.validate_access_token.return_value = test_user
        mock_service.logout = AsyncMock()
        mock_get_service.return_value = mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/logout",
                headers={"Authorization": "Bearer valid_access_token"},
            )

        assert response.status_code == status.HTTP_200_OK
        assert "Successfully logged out" in response.json()["message"]

    @pytest.mark.asyncio
    async def test_logout_without_token(self):
        """Test logout without authentication."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/auth/logout")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    @patch("app.api.deps.get_auth_service")
    async def test_logout_invalid_token(self, mock_get_service):
        """Test logout with invalid token."""
        mock_service = AsyncMock()
        mock_service.validate_access_token.side_effect = InvalidTokenError("Invalid token")
        mock_get_service.return_value = mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/logout",
                headers={"Authorization": "Bearer invalid_token"},
            )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# =============================================================================
# API Endpoint Tests - Get Current User (mocked)
# =============================================================================


class TestGetMeEndpoint:
    """Test GET /api/v1/auth/me endpoint."""

    @pytest.mark.asyncio
    @patch("app.api.deps.get_auth_service")
    async def test_get_me_success(self, mock_get_service, test_user):
        """Test getting current user profile."""
        mock_service = AsyncMock()
        mock_service.validate_access_token.return_value = test_user
        mock_get_service.return_value = mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": "Bearer valid_access_token"},
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["email"] == test_user.email
        assert "id" in data
        assert "is_verified" in data
        assert "is_premium" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_get_me_without_token(self):
        """Test getting profile without authentication."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/auth/me")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    @patch("app.api.deps.get_auth_service")
    async def test_get_me_invalid_token(self, mock_get_service):
        """Test getting profile with invalid token."""
        mock_service = AsyncMock()
        mock_service.validate_access_token.side_effect = InvalidTokenError("Invalid token")
        mock_get_service.return_value = mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": "Bearer invalid.token.here"},
            )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# =============================================================================
# Schema Validation Tests
# =============================================================================


class TestSchemaValidation:
    """Tests for Pydantic schema validation."""

    def test_user_register_schema_valid(self):
        """Test valid registration schema."""
        from app.schemas.auth import UserRegisterRequest

        data = UserRegisterRequest(
            email="test@example.com",
            password="ValidPassword123",
        )
        assert data.email == "test@example.com"
        assert data.password == "ValidPassword123"

    def test_user_register_schema_invalid_email(self):
        """Test invalid email raises error."""
        from app.schemas.auth import UserRegisterRequest

        with pytest.raises(ValueError):
            UserRegisterRequest(
                email="not_an_email",
                password="ValidPassword123",
            )

    def test_user_register_schema_weak_password(self):
        """Test weak password raises error."""
        from app.schemas.auth import UserRegisterRequest

        with pytest.raises(ValueError):
            UserRegisterRequest(
                email="test@example.com",
                password="weak",
            )

    def test_token_response_schema(self):
        """Test TokenResponse schema."""
        from app.schemas.auth import TokenResponse

        response = TokenResponse(
            access_token="abc123",
            refresh_token="xyz789",
            token_type="bearer",
            expires_in=86400,
        )
        assert response.access_token == "abc123"
        assert response.refresh_token == "xyz789"
        assert response.token_type == "bearer"
        assert response.expires_in == 86400

    def test_user_response_schema(self):
        """Test UserResponse schema."""
        from app.schemas.auth import UserResponse

        response = UserResponse(
            id=1,
            email="test@example.com",
            is_verified=True,
            is_premium=False,
            created_at=datetime.now(timezone.utc),
            updated_at=None,
        )
        assert response.id == 1
        assert response.email == "test@example.com"
        assert response.is_verified is True
        assert response.is_premium is False
