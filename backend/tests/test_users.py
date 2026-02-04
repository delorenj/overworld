"""Tests for user management endpoints.

Tests cover:
- Disconnecting a linked social account
- Preventing disconnection of the only login method
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models import User
from app.api.deps import get_db


@pytest.fixture
def test_user_linked():
    """Create a test user linked to Google."""
    return User(
        id=1,
        email="test@example.com",
        password_hash="$2b$12$...",
        is_verified=True,
        oauth_provider="google",
        oauth_id="google-123",
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def test_user_only_oauth():
    """Create a test user with only OAuth (no password)."""
    return User(
        id=2,
        email="oauth@example.com",
        password_hash=None,
        is_verified=True,
        oauth_provider="google",
        oauth_id="google-123",
        created_at=datetime.now(timezone.utc),
    )


class TestDisconnectAccountEndpoint:
    """Test DELETE /api/v1/users/me/accounts/{provider} endpoint."""

    @pytest.mark.asyncio
    @patch("app.api.deps.get_auth_service")
    async def test_disconnect_success(self, mock_get_service, test_user_linked):
        """Test successful disconnection of a linked account."""
        mock_service = AsyncMock()
        mock_service.validate_access_token.return_value = test_user_linked
        mock_get_service.return_value = mock_service

        # Mock DB session
        mock_db = AsyncMock()
        mock_db.add = MagicMock()  # add is synchronous
        mock_db.commit = AsyncMock()

        async def override_get_db():
            yield mock_db

        # Save existing overrides
        original_overrides = app.dependency_overrides.copy()
        app.dependency_overrides[get_db] = override_get_db

        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.delete(
                    "/api/v1/users/me/accounts/google",
                    headers={"Authorization": "Bearer valid_token"},
                )

            assert response.status_code == status.HTTP_204_NO_CONTENT
            assert test_user_linked.oauth_provider is None
            assert test_user_linked.oauth_id is None
            mock_db.commit.assert_called_once()
        finally:
            # Restore original overrides
            app.dependency_overrides = original_overrides

    @pytest.mark.asyncio
    @patch("app.api.deps.get_auth_service")
    async def test_disconnect_not_linked(self, mock_get_service, test_user_linked):
        """Test disconnecting an account that is not linked."""
        mock_service = AsyncMock()
        mock_service.validate_access_token.return_value = test_user_linked
        mock_get_service.return_value = mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete(
                "/api/v1/users/me/accounts/github",
                headers={"Authorization": "Bearer valid_token"},
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "not linked" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch("app.api.deps.get_auth_service")
    async def test_disconnect_only_login_method(self, mock_get_service, test_user_only_oauth):
        """Test disconnecting the only login method (OAuth w/o password)."""
        mock_service = AsyncMock()
        mock_service.validate_access_token.return_value = test_user_only_oauth
        mock_get_service.return_value = mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete(
                "/api/v1/users/me/accounts/google",
                headers={"Authorization": "Bearer valid_token"},
            )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "only login method" in response.json()["detail"]
