"""Tests for Stripe payment integration.

This module tests:
- Token package listing
- Checkout session creation
- Webhook signature verification
- Webhook event processing
- Rate limiting for anonymous users
- Token balance updates after payment
"""

import hashlib
import json
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import stripe
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.schemas.stripe import TokenPackage
from app.services.stripe_service import (
    StripeService,
    InvalidPackageError,
    PaymentProcessingError,
    WebhookVerificationError,
    TOKEN_PACKAGES,
    PACKAGE_LOOKUP,
)
from app.middleware.rate_limit import (
    AnonymousRateLimiter,
    RateLimitExceeded,
    RATE_LIMIT_PREFIX,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_stripe_checkout_session():
    """Mock Stripe checkout session object."""
    return {
        "id": "cs_test_123456789",
        "url": "https://checkout.stripe.com/c/pay/cs_test_123456789",
        "expires_at": int(datetime.now(timezone.utc).timestamp()) + 3600,
        "metadata": {
            "user_id": "1",
            "package_id": "starter",
            "tokens": "1000",
        },
        "payment_status": "paid",
        "customer_details": {
            "email": "test@example.com",
        },
    }


@pytest.fixture
def mock_stripe_event(mock_stripe_checkout_session):
    """Mock Stripe webhook event."""
    return {
        "id": "evt_test_123456789",
        "type": "checkout.session.completed",
        "data": {
            "object": mock_stripe_checkout_session,
        },
    }


@pytest.fixture
def mock_redis():
    """Mock Redis client for rate limiting tests."""
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.incr = AsyncMock(return_value=1)
    redis_mock.expire = AsyncMock(return_value=True)
    redis_mock.ttl = AsyncMock(return_value=86400)
    return redis_mock


# ============================================================================
# Token Package Tests
# ============================================================================


class TestTokenPackages:
    """Tests for token package management."""

    def test_package_definitions(self):
        """Test that all packages are properly defined."""
        assert len(TOKEN_PACKAGES) >= 3
        assert len(TOKEN_PACKAGES) == len(PACKAGE_LOOKUP)

        for package in TOKEN_PACKAGES:
            assert package.id
            assert package.name
            assert package.tokens > 0
            assert package.price_cents >= 0
            assert package.currency == "usd"

    def test_package_lookup(self):
        """Test package lookup by ID."""
        for package in TOKEN_PACKAGES:
            found = PACKAGE_LOOKUP.get(package.id)
            assert found is not None
            assert found.id == package.id
            assert found.tokens == package.tokens

    def test_package_price_display(self):
        """Test price display formatting."""
        package = TokenPackage(
            id="test",
            name="Test",
            tokens=1000,
            price_cents=500,
            currency="usd",
        )
        assert package.price_display == "$5.00"

        package2 = TokenPackage(
            id="test2",
            name="Test 2",
            tokens=5000,
            price_cents=1999,
            currency="usd",
        )
        assert package2.price_display == "$19.99"

    def test_package_price_per_token(self):
        """Test price per token calculation."""
        package = TokenPackage(
            id="test",
            name="Test",
            tokens=1000,
            price_cents=500,
            currency="usd",
        )
        assert package.price_per_token == 0.5  # 0.5 cents per token

    def test_get_packages(self):
        """Test getting all packages."""
        service = StripeService(db=Mock())
        packages = service.get_packages()

        assert isinstance(packages, list)
        assert len(packages) == len(TOKEN_PACKAGES)
        assert all(isinstance(p, TokenPackage) for p in packages)

    def test_get_package_by_id(self):
        """Test getting a specific package by ID."""
        service = StripeService(db=Mock())
        package = service.get_package("starter")

        assert package.id == "starter"
        assert package.tokens == 1000

    def test_get_invalid_package(self):
        """Test getting an invalid package raises error."""
        service = StripeService(db=Mock())

        with pytest.raises(InvalidPackageError) as exc_info:
            service.get_package("invalid_package_id")

        assert "Invalid package ID" in str(exc_info.value)


# ============================================================================
# Checkout Session Tests
# ============================================================================


class TestCheckoutSession:
    """Tests for checkout session creation."""

    @pytest.mark.asyncio
    @patch("stripe.checkout.Session.create")
    async def test_create_checkout_session_success(
        self,
        mock_stripe_create,
        mock_stripe_checkout_session,
    ):
        """Test successful checkout session creation."""
        mock_stripe_create.return_value = Mock(**mock_stripe_checkout_session)

        db = Mock(spec=AsyncSession)
        service = StripeService(db)

        session_id, checkout_url, expires_at = await service.create_checkout_session(
            user_id=1,
            package_id="starter",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )

        assert session_id == "cs_test_123456789"
        assert checkout_url == "https://checkout.stripe.com/c/pay/cs_test_123456789"
        assert expires_at > 0

        # Verify Stripe API was called correctly
        mock_stripe_create.assert_called_once()
        call_kwargs = mock_stripe_create.call_args.kwargs
        assert call_kwargs["mode"] == "payment"
        assert call_kwargs["metadata"]["user_id"] == "1"
        assert call_kwargs["metadata"]["package_id"] == "starter"

    @pytest.mark.asyncio
    async def test_create_checkout_invalid_package(self):
        """Test checkout with invalid package raises error."""
        db = Mock(spec=AsyncSession)
        service = StripeService(db)

        with pytest.raises(InvalidPackageError):
            await service.create_checkout_session(
                user_id=1,
                package_id="invalid",
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
            )

    @pytest.mark.asyncio
    @patch("stripe.checkout.Session.create")
    async def test_create_checkout_stripe_error(self, mock_stripe_create):
        """Test checkout handles Stripe API errors."""
        mock_stripe_create.side_effect = stripe.error.StripeError("API error")

        db = Mock(spec=AsyncSession)
        service = StripeService(db)

        with pytest.raises(Exception) as exc_info:
            await service.create_checkout_session(
                user_id=1,
                package_id="starter",
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
            )

        assert "Failed to create checkout session" in str(exc_info.value)


# ============================================================================
# Webhook Signature Verification Tests
# ============================================================================


class TestWebhookVerification:
    """Tests for webhook signature verification."""

    def test_verify_webhook_signature_success(self):
        """Test successful webhook signature verification."""
        payload = json.dumps({"test": "data"}).encode()
        secret = "whsec_test_secret"

        # Generate valid signature
        timestamp = int(time.time())
        signed_payload = f"{timestamp}.{payload.decode()}"
        signature = (
            f"t={timestamp},"
            f"v1={hashlib.sha256((signed_payload).encode()).hexdigest()}"
        )

        with patch("stripe.Webhook.construct_event") as mock_construct:
            mock_event = {"id": "evt_test", "type": "test"}
            mock_construct.return_value = mock_event

            event = StripeService.verify_webhook_signature(
                payload=payload,
                signature=signature,
                webhook_secret=secret,
            )

            assert event == mock_event
            mock_construct.assert_called_once_with(payload, signature, secret)

    def test_verify_webhook_invalid_signature(self):
        """Test webhook with invalid signature raises error."""
        payload = json.dumps({"test": "data"}).encode()
        secret = "whsec_test_secret"
        invalid_signature = "invalid_signature"

        with patch("stripe.Webhook.construct_event") as mock_construct:
            mock_construct.side_effect = stripe.error.SignatureVerificationError(
                "Invalid signature", "sig_header"
            )

            with pytest.raises(WebhookVerificationError):
                StripeService.verify_webhook_signature(
                    payload=payload,
                    signature=invalid_signature,
                    webhook_secret=secret,
                )

    def test_verify_webhook_missing_secret(self):
        """Test webhook verification without secret raises error."""
        payload = json.dumps({"test": "data"}).encode()
        signature = "test_signature"

        with patch.object(settings, "STRIPE_WEBHOOK_SECRET", ""):
            with pytest.raises(WebhookVerificationError) as exc_info:
                StripeService.verify_webhook_signature(
                    payload=payload,
                    signature=signature,
                )

            assert "not configured" in str(exc_info.value)


# ============================================================================
# Webhook Event Processing Tests
# ============================================================================


class TestWebhookProcessing:
    """Tests for webhook event processing."""

    @pytest.mark.asyncio
    async def test_process_checkout_completed_success(
        self,
        mock_stripe_event,
    ):
        """Test successful processing of checkout.session.completed."""
        db = AsyncMock(spec=AsyncSession)
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        db.add = AsyncMock()

        service = StripeService(db)

        # Mock token service
        with patch.object(service.token_service, "add_tokens") as mock_add_tokens:
            mock_add_tokens.return_value = 1100  # New balance

            result = await service.process_checkout_completed(mock_stripe_event)

            assert result["success"] is True
            assert result["tokens_granted"] == 1000
            assert result["new_balance"] == 1100
            assert result["user_id"] == "1"

            # Verify token service was called correctly
            mock_add_tokens.assert_called_once()
            call_kwargs = mock_add_tokens.call_args.kwargs
            assert call_kwargs["user_id"] == 1
            assert call_kwargs["amount"] == 1000
            assert call_kwargs["reason"] == TransactionType.PURCHASE
            assert call_kwargs["stripe_event_id"] == "evt_test_123456789"

    @pytest.mark.asyncio
    async def test_process_checkout_missing_metadata(self, mock_stripe_event):
        """Test checkout processing with missing metadata."""
        # Remove metadata
        mock_stripe_event["data"]["object"]["metadata"] = {}

        db = AsyncMock(spec=AsyncSession)
        service = StripeService(db)

        with pytest.raises(PaymentProcessingError) as exc_info:
            await service.process_checkout_completed(mock_stripe_event)

        assert "Missing metadata" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_process_checkout_unpaid_status(self, mock_stripe_event):
        """Test checkout processing with unpaid status."""
        # Change payment status
        mock_stripe_event["data"]["object"]["payment_status"] = "unpaid"

        db = AsyncMock(spec=AsyncSession)
        service = StripeService(db)

        result = await service.process_checkout_completed(mock_stripe_event)

        assert result["success"] is False
        assert "unpaid" in result["reason"]

    @pytest.mark.asyncio
    async def test_process_checkout_duplicate_event(self, mock_stripe_event):
        """Test checkout processing with duplicate event (idempotency)."""
        db = AsyncMock(spec=AsyncSession)
        service = StripeService(db)

        # Mock duplicate constraint violation
        with patch.object(service.token_service, "add_tokens") as mock_add_tokens:
            mock_add_tokens.side_effect = Exception("unique constraint")

            result = await service.process_checkout_completed(mock_stripe_event)

            assert result["success"] is True
            assert result.get("duplicate") is True

    @pytest.mark.asyncio
    async def test_process_payment_intent_succeeded(self):
        """Test processing of payment_intent.succeeded event."""
        event = {
            "id": "evt_test_pi",
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_test",
                    "amount": 500,
                    "currency": "usd",
                }
            },
        }

        db = AsyncMock(spec=AsyncSession)
        service = StripeService(db)

        result = await service.process_payment_intent_succeeded(event)

        assert result["success"] is True
        assert result["event_type"] == "payment_intent.succeeded"

    @pytest.mark.asyncio
    async def test_process_webhook_event_routing(self, mock_stripe_event):
        """Test webhook event routing to correct handler."""
        db = AsyncMock(spec=AsyncSession)
        service = StripeService(db)

        with patch.object(
            service, "process_checkout_completed"
        ) as mock_checkout:
            mock_checkout.return_value = {"success": True}

            result = await service.process_webhook_event(mock_stripe_event)

            assert result["success"] is True
            mock_checkout.assert_called_once_with(mock_stripe_event)


# ============================================================================
# Rate Limiting Tests
# ============================================================================


class TestRateLimiting:
    """Tests for anonymous user rate limiting."""

    @pytest.mark.asyncio
    async def test_rate_limiter_initialization(self, mock_redis):
        """Test rate limiter initialization."""
        limiter = AnonymousRateLimiter(redis_client=mock_redis, limit=3)

        assert limiter.redis == mock_redis
        assert limiter.limit == 3

    @pytest.mark.asyncio
    async def test_client_identifier_generation(self, mock_redis):
        """Test client identifier generation."""
        limiter = AnonymousRateLimiter(redis_client=mock_redis)

        # Mock request
        request = Mock()
        request.client = Mock(host="192.168.1.1")
        request.headers = {}

        identifier = limiter._get_client_identifier(request)

        assert identifier.startswith(RATE_LIMIT_PREFIX)
        assert len(identifier) > len(RATE_LIMIT_PREFIX)  # Includes hash

    @pytest.mark.asyncio
    async def test_client_identifier_with_fingerprint(self, mock_redis):
        """Test client identifier with browser fingerprint."""
        limiter = AnonymousRateLimiter(redis_client=mock_redis)

        request = Mock()
        request.client = Mock(host="192.168.1.1")
        request.headers = {}

        id1 = limiter._get_client_identifier(request)
        id2 = limiter._get_client_identifier(request, fingerprint="test123")

        assert id1 != id2  # Different fingerprints should produce different IDs

    @pytest.mark.asyncio
    async def test_check_rate_limit_allowed(self, mock_redis):
        """Test rate limit check when within limit."""
        mock_redis.get.return_value = "2"  # 2 requests used

        limiter = AnonymousRateLimiter(redis_client=mock_redis, limit=3)
        request = Mock(client=Mock(host="192.168.1.1"), headers={})

        allowed, current, remaining = await limiter.check_rate_limit(request)

        assert allowed is True
        assert current == 2
        assert remaining == 1

    @pytest.mark.asyncio
    async def test_check_rate_limit_exceeded(self, mock_redis):
        """Test rate limit check when limit exceeded."""
        mock_redis.get.return_value = "3"  # 3 requests used (limit reached)

        limiter = AnonymousRateLimiter(redis_client=mock_redis, limit=3)
        request = Mock(client=Mock(host="192.168.1.1"), headers={})

        allowed, current, remaining = await limiter.check_rate_limit(request)

        assert allowed is False
        assert current == 3
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_increment_usage(self, mock_redis):
        """Test usage counter increment."""
        mock_redis.incr.return_value = 1

        limiter = AnonymousRateLimiter(redis_client=mock_redis, limit=3)
        request = Mock(client=Mock(host="192.168.1.1"), headers={})

        new_count = await limiter.increment_usage(request)

        assert new_count == 1
        mock_redis.incr.assert_called_once()
        mock_redis.expire.assert_called_once()  # TTL set on first use

    @pytest.mark.asyncio
    async def test_enforce_rate_limit_allowed(self, mock_redis):
        """Test enforce rate limit when within limit."""
        mock_redis.get.return_value = "1"

        limiter = AnonymousRateLimiter(redis_client=mock_redis, limit=3)
        request = Mock(client=Mock(host="192.168.1.1"), headers={})

        result = await limiter.enforce_rate_limit(request)

        assert result["limit"] == 3
        assert result["remaining"] == 2
        assert result["current"] == 1

    @pytest.mark.asyncio
    async def test_enforce_rate_limit_raises_exception(self, mock_redis):
        """Test enforce rate limit raises exception when exceeded."""
        mock_redis.get.return_value = "3"
        mock_redis.ttl.return_value = 3600

        limiter = AnonymousRateLimiter(redis_client=mock_redis, limit=3)
        request = Mock(client=Mock(host="192.168.1.1"), headers={})

        with pytest.raises(RateLimitExceeded) as exc_info:
            await limiter.enforce_rate_limit(request)

        assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "Retry-After" in exc_info.value.headers

    @pytest.mark.asyncio
    async def test_rate_limiter_redis_unavailable(self):
        """Test rate limiter graceful degradation when Redis unavailable."""
        limiter = AnonymousRateLimiter(redis_client=None, limit=3)
        request = Mock(client=Mock(host="192.168.1.1"), headers={})

        # Should not raise error, allows request
        allowed, current, remaining = await limiter.check_rate_limit(request)

        assert allowed is True
        assert current == 0
        assert remaining == 3


# ============================================================================
# Integration Tests (require test database)
# ============================================================================


class TestStripeIntegration:
    """Integration tests for Stripe service with database."""

    @pytest.mark.asyncio
    async def test_full_payment_flow(self, db_session: AsyncSession, test_user: User):
        """Test complete payment flow from checkout to token grant."""
        # This test would require a test database setup
        # Simplified version shown here

        service = StripeService(db_session)

        # Create checkout session (mocked)
        with patch("stripe.checkout.Session.create") as mock_create:
            mock_create.return_value = Mock(
                id="cs_test",
                url="https://checkout.stripe.com/test",
                expires_at=int(time.time()) + 3600,
            )

            session_id, url, expires = await service.create_checkout_session(
                user_id=test_user.id,
                package_id="starter",
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
            )

            assert session_id == "cs_test"

        # Process webhook (mocked)
        event = {
            "id": "evt_integration_test",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": session_id,
                    "payment_status": "paid",
                    "metadata": {
                        "user_id": str(test_user.id),
                        "package_id": "starter",
                        "tokens": "1000",
                    },
                    "customer_details": {
                        "email": test_user.email,
                    },
                }
            },
        }

        result = await service.process_checkout_completed(event)

        assert result["success"] is True
        assert result["tokens_granted"] == 1000
