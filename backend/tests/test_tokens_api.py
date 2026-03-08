"""API tests for token balance/credit endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import settings
from app.main import app
from app.models.user import User


@pytest.fixture
async def api_client(db_session: AsyncSession):
    """Create API client with test DB dependency override."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_balance_anonymous(api_client: AsyncClient):
    """Anonymous callers should receive free-tier balance details."""
    response = await api_client.get(
        "/api/v1/tokens/balance",
        headers={"X-Session-ID": "anon-session-1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["operation"] == "export"
    assert payload["limit"] >= 1
    assert payload["remaining"] == payload["limit"]


@pytest.mark.asyncio
async def test_admin_credit_tokens(api_client: AsyncClient, db_session: AsyncSession):
    """Admin endpoint should credit user tokens when key is valid."""
    original_admin_key = settings.TOKEN_ADMIN_API_KEY
    settings.TOKEN_ADMIN_API_KEY = "test-admin-key"

    try:
        user = User(email="credit-user@example.com", password_hash="hash", is_verified=True)
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        response = await api_client.post(
            "/api/v1/tokens/credit",
            headers={"X-Admin-Key": "test-admin-key"},
            json={
                "user_id": user.id,
                "amount": 25,
                "reason": "manual_adjustment",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["user_id"] == user.id
        assert payload["amount"] == 25
        assert payload["new_balance"] >= 25
    finally:
        settings.TOKEN_ADMIN_API_KEY = original_admin_key
