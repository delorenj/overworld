"""Comprehensive tests for OAuth2 authentication.

Tests cover:
- OAuth URL generation (Google and GitHub)
- Token exchange (mocked)
- User info fetching (mocked)
- Account linking scenarios
- Error handling
- API endpoints
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.auth_service import (
    AuthService,
    OAuthAccountLinkError,
    pwd_context,
)
from app.services.oauth import (
    OAuthConfigurationError,
    OAuthProvider,
    OAuthTokenError,
    OAuthUserInfo,
    OAuthUserInfoError,
    generate_oauth_state,
)
from app.services.oauth.github import GITHUB_AUTH_URL, GitHubOAuthProvider
from app.services.oauth.google import GOOGLE_AUTH_URL, GoogleOAuthProvider

# =============================================================================
# Fixtures
# =============================================================================


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
def google_user_info():
    """Create test Google OAuth user info."""
    return OAuthUserInfo(
        provider=OAuthProvider.GOOGLE,
        provider_user_id="google-123456",
        email="testuser@gmail.com",
        name="Test User",
        picture_url="https://lh3.googleusercontent.com/test",
        email_verified=True,
    )


@pytest.fixture
def github_user_info():
    """Create test GitHub OAuth user info."""
    return OAuthUserInfo(
        provider=OAuthProvider.GITHUB,
        provider_user_id="github-789012",
        email="testuser@github.com",
        name="Test GitHub User",
        picture_url="https://avatars.githubusercontent.com/test",
        email_verified=True,
    )


@pytest.fixture
def existing_user():
    """Create a test user with email/password auth."""
    password = "TestPassword123"
    hashed_password = pwd_context.hash(password)

    user = User(
        id=1,
        email="existing@example.com",
        password_hash=hashed_password,
        oauth_provider=None,
        oauth_id=None,
        is_verified=False,
        is_premium=False,
        created_at=datetime.now(UTC),
    )
    return user


@pytest.fixture
def oauth_user():
    """Create a test user with OAuth auth."""
    user = User(
        id=2,
        email="oauth@example.com",
        password_hash=None,
        oauth_provider="google",
        oauth_id="google-existing-123",
        is_verified=True,
        is_premium=False,
        created_at=datetime.now(UTC),
    )
    return user


# =============================================================================
# Unit Tests - OAuth State Generation
# =============================================================================


class TestOAuthStateGeneration:
    """Test OAuth state parameter generation."""

    def test_generate_oauth_state_length(self):
        """Test that generated state has appropriate length."""
        state = generate_oauth_state()
        # URL-safe base64 of 24 bytes = 32 characters
        assert len(state) == 32

    def test_generate_oauth_state_uniqueness(self):
        """Test that generated states are unique."""
        states = [generate_oauth_state() for _ in range(100)]
        assert len(set(states)) == 100  # All unique

    def test_generate_oauth_state_url_safe(self):
        """Test that generated state is URL-safe."""
        state = generate_oauth_state()
        # URL-safe characters only
        import re
        assert re.match(r'^[A-Za-z0-9_-]+$', state)


# =============================================================================
# Unit Tests - Google OAuth Provider
# =============================================================================


class TestGoogleOAuthProvider:
    """Test Google OAuth provider."""

    @patch("app.services.oauth.google.settings")
    def test_init_without_credentials_raises_error(self, mock_settings):
        """Test that missing credentials raise configuration error."""
        mock_settings.GOOGLE_CLIENT_ID = ""
        mock_settings.GOOGLE_CLIENT_SECRET = ""

        with pytest.raises(OAuthConfigurationError):
            GoogleOAuthProvider()

    @patch("app.services.oauth.google.settings")
    def test_get_authorization_url(self, mock_settings):
        """Test authorization URL generation."""
        mock_settings.GOOGLE_CLIENT_ID = "test-client-id"
        mock_settings.GOOGLE_CLIENT_SECRET = "test-client-secret"
        mock_settings.OAUTH_REDIRECT_URL = "http://localhost:8000/api/v1/auth"

        provider = GoogleOAuthProvider()
        state = "test-state-123"
        url = provider.get_authorization_url(state)

        # Verify URL contains required parameters
        assert GOOGLE_AUTH_URL in url
        assert "client_id=test-client-id" in url
        assert "state=test-state-123" in url
        assert "response_type=code" in url
        assert "scope=" in url
        assert "redirect_uri=" in url

    @patch("app.services.oauth.google.settings")
    def test_provider_name(self, mock_settings):
        """Test provider name property."""
        mock_settings.GOOGLE_CLIENT_ID = "test-client-id"
        mock_settings.GOOGLE_CLIENT_SECRET = "test-client-secret"
        mock_settings.OAUTH_REDIRECT_URL = "http://localhost:8000/api/v1/auth"

        provider = GoogleOAuthProvider()
        assert provider.provider_name == OAuthProvider.GOOGLE

    @pytest.mark.asyncio
    @patch("app.services.oauth.google.settings")
    @patch("app.services.oauth.google.httpx.AsyncClient")
    async def test_exchange_code_for_token_success(self, mock_client_class, mock_settings):
        """Test successful token exchange."""
        mock_settings.GOOGLE_CLIENT_ID = "test-client-id"
        mock_settings.GOOGLE_CLIENT_SECRET = "test-client-secret"
        mock_settings.OAUTH_REDIRECT_URL = "http://localhost:8000/api/v1/auth"

        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "google-access-token-123",
            "token_type": "Bearer",
            "expires_in": 3600,
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client_class.return_value = mock_client

        provider = GoogleOAuthProvider()
        token = await provider.exchange_code_for_token("auth-code-123")

        assert token == "google-access-token-123"

    @pytest.mark.asyncio
    @patch("app.services.oauth.google.settings")
    @patch("app.services.oauth.google.httpx.AsyncClient")
    async def test_exchange_code_for_token_error(self, mock_client_class, mock_settings):
        """Test token exchange error handling."""
        mock_settings.GOOGLE_CLIENT_ID = "test-client-id"
        mock_settings.GOOGLE_CLIENT_SECRET = "test-client-secret"
        mock_settings.OAUTH_REDIRECT_URL = "http://localhost:8000/api/v1/auth"

        # Mock error response
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": "invalid_grant",
            "error_description": "Code has expired",
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client_class.return_value = mock_client

        provider = GoogleOAuthProvider()

        with pytest.raises(OAuthTokenError) as exc_info:
            await provider.exchange_code_for_token("invalid-code")

        assert "Code has expired" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("app.services.oauth.google.settings")
    @patch("app.services.oauth.google.httpx.AsyncClient")
    async def test_get_user_info_success(self, mock_client_class, mock_settings):
        """Test successful user info retrieval."""
        mock_settings.GOOGLE_CLIENT_ID = "test-client-id"
        mock_settings.GOOGLE_CLIENT_SECRET = "test-client-secret"
        mock_settings.OAUTH_REDIRECT_URL = "http://localhost:8000/api/v1/auth"

        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "123456789",
            "email": "test@gmail.com",
            "verified_email": True,
            "name": "Test User",
            "picture": "https://lh3.googleusercontent.com/test",
        }

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client_class.return_value = mock_client

        provider = GoogleOAuthProvider()
        user_info = await provider.get_user_info("access-token-123")

        assert user_info.provider == OAuthProvider.GOOGLE
        assert user_info.provider_user_id == "123456789"
        assert user_info.email == "test@gmail.com"
        assert user_info.name == "Test User"
        assert user_info.email_verified is True

    @pytest.mark.asyncio
    @patch("app.services.oauth.google.settings")
    @patch("app.services.oauth.google.httpx.AsyncClient")
    async def test_get_user_info_missing_email(self, mock_client_class, mock_settings):
        """Test error when email is missing."""
        mock_settings.GOOGLE_CLIENT_ID = "test-client-id"
        mock_settings.GOOGLE_CLIENT_SECRET = "test-client-secret"
        mock_settings.OAUTH_REDIRECT_URL = "http://localhost:8000/api/v1/auth"

        # Mock response without email
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "123456789",
            "name": "Test User",
        }

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client_class.return_value = mock_client

        provider = GoogleOAuthProvider()

        with pytest.raises(OAuthUserInfoError) as exc_info:
            await provider.get_user_info("access-token-123")

        assert "No email" in str(exc_info.value)


# =============================================================================
# Unit Tests - GitHub OAuth Provider
# =============================================================================


class TestGitHubOAuthProvider:
    """Test GitHub OAuth provider."""

    @patch("app.services.oauth.github.settings")
    def test_init_without_credentials_raises_error(self, mock_settings):
        """Test that missing credentials raise configuration error."""
        mock_settings.GITHUB_CLIENT_ID = ""
        mock_settings.GITHUB_CLIENT_SECRET = ""

        with pytest.raises(OAuthConfigurationError):
            GitHubOAuthProvider()

    @patch("app.services.oauth.github.settings")
    def test_get_authorization_url(self, mock_settings):
        """Test authorization URL generation."""
        mock_settings.GITHUB_CLIENT_ID = "test-client-id"
        mock_settings.GITHUB_CLIENT_SECRET = "test-client-secret"
        mock_settings.OAUTH_REDIRECT_URL = "http://localhost:8000/api/v1/auth"

        provider = GitHubOAuthProvider()
        state = "test-state-123"
        url = provider.get_authorization_url(state)

        # Verify URL contains required parameters
        assert GITHUB_AUTH_URL in url
        assert "client_id=test-client-id" in url
        assert "state=test-state-123" in url
        assert "scope=" in url
        assert "redirect_uri=" in url

    @patch("app.services.oauth.github.settings")
    def test_provider_name(self, mock_settings):
        """Test provider name property."""
        mock_settings.GITHUB_CLIENT_ID = "test-client-id"
        mock_settings.GITHUB_CLIENT_SECRET = "test-client-secret"
        mock_settings.OAUTH_REDIRECT_URL = "http://localhost:8000/api/v1/auth"

        provider = GitHubOAuthProvider()
        assert provider.provider_name == OAuthProvider.GITHUB

    @pytest.mark.asyncio
    @patch("app.services.oauth.github.settings")
    @patch("app.services.oauth.github.httpx.AsyncClient")
    async def test_exchange_code_for_token_success(self, mock_client_class, mock_settings):
        """Test successful token exchange."""
        mock_settings.GITHUB_CLIENT_ID = "test-client-id"
        mock_settings.GITHUB_CLIENT_SECRET = "test-client-secret"
        mock_settings.OAUTH_REDIRECT_URL = "http://localhost:8000/api/v1/auth"

        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "github-access-token-123",
            "token_type": "bearer",
            "scope": "read:user,user:email",
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client_class.return_value = mock_client

        provider = GitHubOAuthProvider()
        token = await provider.exchange_code_for_token("auth-code-123")

        assert token == "github-access-token-123"

    @pytest.mark.asyncio
    @patch("app.services.oauth.github.settings")
    @patch("app.services.oauth.github.httpx.AsyncClient")
    async def test_exchange_code_for_token_error(self, mock_client_class, mock_settings):
        """Test token exchange error handling."""
        mock_settings.GITHUB_CLIENT_ID = "test-client-id"
        mock_settings.GITHUB_CLIENT_SECRET = "test-client-secret"
        mock_settings.OAUTH_REDIRECT_URL = "http://localhost:8000/api/v1/auth"

        # Mock error response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "error": "bad_verification_code",
            "error_description": "The code passed is incorrect or expired.",
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client_class.return_value = mock_client

        provider = GitHubOAuthProvider()

        with pytest.raises(OAuthTokenError) as exc_info:
            await provider.exchange_code_for_token("invalid-code")

        assert "incorrect or expired" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("app.services.oauth.github.settings")
    @patch("app.services.oauth.github.httpx.AsyncClient")
    async def test_get_user_info_success(self, mock_client_class, mock_settings):
        """Test successful user info retrieval."""
        mock_settings.GITHUB_CLIENT_ID = "test-client-id"
        mock_settings.GITHUB_CLIENT_SECRET = "test-client-secret"
        mock_settings.OAUTH_REDIRECT_URL = "http://localhost:8000/api/v1/auth"

        # Mock HTTP response for user endpoint
        mock_user_response = MagicMock()
        mock_user_response.status_code = 200
        mock_user_response.json.return_value = {
            "id": 12345678,
            "login": "testuser",
            "name": "Test User",
            "email": "test@github.com",
            "avatar_url": "https://avatars.githubusercontent.com/test",
        }

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_user_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client_class.return_value = mock_client

        provider = GitHubOAuthProvider()
        user_info = await provider.get_user_info("access-token-123")

        assert user_info.provider == OAuthProvider.GITHUB
        assert user_info.provider_user_id == "12345678"
        assert user_info.email == "test@github.com"
        assert user_info.name == "Test User"

    @pytest.mark.asyncio
    @patch("app.services.oauth.github.settings")
    @patch("app.services.oauth.github.httpx.AsyncClient")
    async def test_get_user_info_private_email(self, mock_client_class, mock_settings):
        """Test fetching email from emails endpoint for private email users."""
        mock_settings.GITHUB_CLIENT_ID = "test-client-id"
        mock_settings.GITHUB_CLIENT_SECRET = "test-client-secret"
        mock_settings.OAUTH_REDIRECT_URL = "http://localhost:8000/api/v1/auth"

        # Mock user response without email (private)
        mock_user_response = MagicMock()
        mock_user_response.status_code = 200
        mock_user_response.json.return_value = {
            "id": 12345678,
            "login": "testuser",
            "name": "Test User",
            "email": None,
            "avatar_url": "https://avatars.githubusercontent.com/test",
        }

        # Mock emails response
        mock_emails_response = MagicMock()
        mock_emails_response.status_code = 200
        mock_emails_response.json.return_value = [
            {"email": "secondary@example.com", "primary": False, "verified": True},
            {"email": "primary@example.com", "primary": True, "verified": True},
        ]

        mock_client = AsyncMock()
        # First call is user, second is emails
        mock_client.get.side_effect = [mock_user_response, mock_emails_response]
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client_class.return_value = mock_client

        provider = GitHubOAuthProvider()
        user_info = await provider.get_user_info("access-token-123")

        assert user_info.email == "primary@example.com"
        assert user_info.email_verified is True


# =============================================================================
# Unit Tests - Auth Service OAuth Methods
# =============================================================================


class TestAuthServiceOAuth:
    """Test AuthService OAuth methods."""

    @pytest.mark.asyncio
    async def test_authenticate_oauth_new_user(self, mock_db, auth_service, google_user_info):
        """Test OAuth authentication creates new user."""
        # Mock no existing users
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        # Mock refresh to set user id
        async def set_user_id(user):
            user.id = 1

        mock_db.refresh = AsyncMock(side_effect=set_user_id)

        user = await auth_service.authenticate_oauth_user(google_user_info)

        assert user.email == google_user_info.email
        assert user.oauth_provider == google_user_info.provider.value
        assert user.oauth_id == google_user_info.provider_user_id
        assert user.password_hash is None
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_authenticate_oauth_existing_oauth_user(
        self, mock_db, auth_service, google_user_info, oauth_user
    ):
        """Test OAuth authentication returns existing OAuth user."""
        # Set up the oauth_user to match the google_user_info
        oauth_user.oauth_provider = "google"
        oauth_user.oauth_id = google_user_info.provider_user_id
        oauth_user.email = google_user_info.email

        # Mock existing OAuth user found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = oauth_user
        mock_db.execute.return_value = mock_result

        user = await auth_service.authenticate_oauth_user(google_user_info)

        assert user.id == oauth_user.id
        # No new user should be created
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_authenticate_oauth_link_to_existing_email(
        self, mock_db, auth_service, google_user_info, existing_user
    ):
        """Test OAuth authentication links to existing email user."""
        # Update google_user_info to match existing user's email
        google_user_info.email = existing_user.email

        # First call: no OAuth user found, second call: email user found
        mock_result_oauth = MagicMock()
        mock_result_oauth.scalar_one_or_none.return_value = None

        mock_result_email = MagicMock()
        mock_result_email.scalar_one_or_none.return_value = existing_user

        mock_db.execute.side_effect = [mock_result_oauth, mock_result_email]

        user = await auth_service.authenticate_oauth_user(google_user_info)

        assert user.id == existing_user.id
        assert user.oauth_provider == google_user_info.provider.value
        assert user.oauth_id == google_user_info.provider_user_id
        # User should be verified since OAuth email is verified
        assert user.is_verified is True

    @pytest.mark.asyncio
    async def test_link_oauth_to_user_different_provider_fails(
        self, mock_db, auth_service, github_user_info, oauth_user
    ):
        """Test linking OAuth fails when different provider is already linked."""
        # oauth_user already has Google linked
        oauth_user.oauth_provider = "google"
        oauth_user.oauth_id = "google-existing-123"

        # Try to link GitHub
        github_user_info.email = oauth_user.email

        with pytest.raises(OAuthAccountLinkError) as exc_info:
            await auth_service._link_oauth_to_user(oauth_user, github_user_info)

        assert "already linked to google" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_link_oauth_to_user_same_provider_different_id_fails(
        self, mock_db, auth_service, google_user_info, oauth_user
    ):
        """Test linking OAuth fails when same provider but different ID."""
        oauth_user.oauth_provider = "google"
        oauth_user.oauth_id = "google-different-id"

        google_user_info.email = oauth_user.email

        with pytest.raises(OAuthAccountLinkError) as exc_info:
            await auth_service._link_oauth_to_user(oauth_user, google_user_info)

        assert "different google account" in str(exc_info.value)


# =============================================================================
# Note: API endpoint tests require the full app to be running.
# These are covered by integration tests. Unit tests above verify
# the core OAuth functionality independently.
# =============================================================================


# =============================================================================
# Integration Tests - OAuth User Info Schema
# =============================================================================


class TestOAuthUserInfoSchema:
    """Test OAuthUserInfo dataclass."""

    def test_oauth_user_info_creation(self):
        """Test OAuthUserInfo creation with all fields."""
        user_info = OAuthUserInfo(
            provider=OAuthProvider.GOOGLE,
            provider_user_id="123456",
            email="test@example.com",
            name="Test User",
            picture_url="https://example.com/photo.jpg",
            email_verified=True,
        )

        assert user_info.provider == OAuthProvider.GOOGLE
        assert user_info.provider_user_id == "123456"
        assert user_info.email == "test@example.com"
        assert user_info.name == "Test User"
        assert user_info.email_verified is True

    def test_oauth_user_info_minimal(self):
        """Test OAuthUserInfo with minimal required fields."""
        user_info = OAuthUserInfo(
            provider=OAuthProvider.GITHUB,
            provider_user_id="789012",
            email="minimal@example.com",
        )

        assert user_info.provider == OAuthProvider.GITHUB
        assert user_info.name is None
        assert user_info.picture_url is None
        assert user_info.email_verified is False


# =============================================================================
# Schema Tests
# =============================================================================


class TestOAuthSchemas:
    """Test OAuth Pydantic schemas."""

    def test_oauth_login_response_schema(self):
        """Test OAuthLoginResponse schema."""
        from app.schemas.auth import OAuthLoginResponse

        response = OAuthLoginResponse(
            authorization_url="https://example.com/oauth/authorize",
            state="random-state-123",
        )

        assert response.authorization_url == "https://example.com/oauth/authorize"
        assert response.state == "random-state-123"

    def test_oauth_callback_request_schema(self):
        """Test OAuthCallbackRequest schema."""
        from app.schemas.auth import OAuthCallbackRequest

        request = OAuthCallbackRequest(
            code="auth-code-123",
            state="state-123",
        )

        assert request.code == "auth-code-123"
        assert request.state == "state-123"
        assert request.error is None

    def test_oauth_callback_request_with_error(self):
        """Test OAuthCallbackRequest with error."""
        from app.schemas.auth import OAuthCallbackRequest

        request = OAuthCallbackRequest(
            code="",
            state="state-123",
            error="access_denied",
            error_description="User denied access",
        )

        assert request.error == "access_denied"
        assert request.error_description == "User denied access"
