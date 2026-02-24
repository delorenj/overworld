"""Integration tests for Stripe subscription flow (mocked).

Tests the complete subscription flow without requiring real Stripe API keys:
1. User requests subscription checkout
2. Stripe webhook fires (checkout.session.completed)
3. User premium status activated
4. User gets watermark-free exports
"""

import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.stripe_service import StripeService


@pytest.mark.asyncio
async def test_subscription_checkout_session_creation(db_session: AsyncSession):
    """Test subscription checkout session creation with mocked Stripe."""
    # Create test user
    user = User(
        email="premium_test@example.com",
        password_hash="hashed",
        is_verified=True,
        is_premium=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Mock Stripe checkout session
    mock_session = MagicMock()
    mock_session.id = "cs_test_123"
    mock_session.url = "https://checkout.stripe.com/test"
    mock_session.expires_at = 1234567890

    with patch("stripe.checkout.Session.create", return_value=mock_session):
        stripe_service = StripeService(db_session)
        
        session_id, checkout_url, expires_at = await stripe_service.create_subscription_session(
            user_id=user.id,
            plan_id="campfire",
            success_url="http://localhost:3000/success",
            cancel_url="http://localhost:3000/cancel",
        )

        assert session_id == "cs_test_123"
        assert checkout_url == "https://checkout.stripe.com/test"
        assert expires_at == 1234567890


@pytest.mark.asyncio
async def test_subscription_webhook_activates_premium(db_session: AsyncSession):
    """Test webhook handler activates premium status on subscription checkout completion."""
    # Create test user
    user = User(
        email="webhook_test@example.com",
        password_hash="hashed",
        is_verified=True,
        is_premium=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Mock Stripe webhook event
    mock_event = {
        "id": "evt_test_123",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_123",
                "payment_status": "paid",
                "metadata": {
                    "user_id": str(user.id),
                    "plan_id": "campfire",
                    "type": "subscription",
                },
            }
        },
    }

    stripe_service = StripeService(db_session)
    result = await stripe_service.process_checkout_completed(mock_event)

    assert result["success"] is True
    assert result["type"] == "subscription"
    assert result["activated"] is True

    # Verify user is now premium
    await db_session.refresh(user)
    assert user.is_premium is True


@pytest.mark.asyncio
async def test_premium_user_gets_clean_export(db_session: AsyncSession, test_theme):
    """Test that premium users can get watermark-free exports."""
    from app.models.map import Map
    from app.services.export_service import ExportService
    from app.models.export import ExportFormat

    # Create premium user
    user = User(
        email="premium_export@example.com",
        password_hash="hashed",
        is_verified=True,
        is_premium=True,  # Premium user
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create a map for the user
    map_obj = Map(
        user_id=user.id,
        theme_id=test_theme.id,
        name="Premium Test Map",
        hierarchy={"title": "Test", "regions": []},
    )
    db_session.add(map_obj)
    await db_session.commit()
    await db_session.refresh(map_obj)

    # Request export without watermark
    export_service = ExportService(db_session)
    export = await export_service.create_export(
        map_id=map_obj.id,
        user_id=user.id,
        format=ExportFormat.PNG,
        resolution=1,
        include_watermark=False,  # User requests no watermark
    )

    # Premium user should get clean export
    assert export.watermarked is False
    assert export.user_id == user.id
    assert export.map_id == map_obj.id


@pytest.mark.asyncio
async def test_free_user_forced_watermark(db_session: AsyncSession, test_theme):
    """Test that free users are forced to have watermarks even if they request clean."""
    from app.models.map import Map
    from app.services.export_service import ExportService
    from app.models.export import ExportFormat

    # Create free user
    user = User(
        email="free_export@example.com",
        password_hash="hashed",
        is_verified=True,
        is_premium=False,  # Free user
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create a map for the user
    map_obj = Map(
        user_id=user.id,
        theme_id=test_theme.id,
        name="Free Test Map",
        hierarchy={"title": "Test", "regions": []},
    )
    db_session.add(map_obj)
    await db_session.commit()
    await db_session.refresh(map_obj)

    # Request export without watermark
    export_service = ExportService(db_session)
    export = await export_service.create_export(
        map_id=map_obj.id,
        user_id=user.id,
        format=ExportFormat.PNG,
        resolution=1,
        include_watermark=False,  # User requests no watermark
    )

    # Free user should be forced to have watermark
    assert export.watermarked is True  # Forced!
    assert export.user_id == user.id
    assert export.map_id == map_obj.id


@pytest.mark.asyncio
async def test_token_purchase_webhook_does_not_activate_premium(db_session: AsyncSession):
    """Test that token purchase webhooks do NOT activate premium status."""
    # Create test user
    user = User(
        email="token_test@example.com",
        password_hash="hashed",
        is_verified=True,
        is_premium=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Mock token purchase webhook event
    mock_event = {
        "id": "evt_token_123",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_token_123",
                "payment_status": "paid",
                "metadata": {
                    "user_id": str(user.id),
                    "package_id": "starter",
                    "type": "token_purchase",
                },
            }
        },
    }

    stripe_service = StripeService(db_session)
    result = await stripe_service.process_checkout_completed(mock_event)

    assert result["success"] is True
    # Should grant tokens, not activate premium
    assert "tokens_granted" in result
    assert result.get("activated") is None

    # Verify user is still free
    await db_session.refresh(user)
    assert user.is_premium is False
