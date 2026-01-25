"""Stripe payment integration service.

This service provides:
- Token package definitions and management
- Checkout session creation for token purchases
- Webhook event processing and signature verification
- Integration with TokenService for balance updates
- Idempotent payment processing
"""

import logging
from typing import Optional

import stripe
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.transaction import TransactionType
from app.schemas.stripe import TokenPackage, WebhookEvent
from app.services.token_service import TokenService

logger = logging.getLogger(__name__)

# Initialize Stripe with API key from settings
stripe.api_key = settings.STRIPE_SECRET_KEY

# Token package definitions
# Price structure: Base rate is ~$0.50 per 1000 tokens, with volume discounts
TOKEN_PACKAGES: list[TokenPackage] = [
    TokenPackage(
        id="starter",
        name="Starter Pack",
        tokens=1000,
        price_cents=500,  # $5.00 - base rate
        popular=False,
        savings_percent=0,
    ),
    TokenPackage(
        id="pro",
        name="Pro Pack",
        tokens=5000,
        price_cents=2000,  # $20.00 - 20% savings
        popular=True,
        savings_percent=20,
    ),
    TokenPackage(
        id="enterprise",
        name="Enterprise Pack",
        tokens=15000,
        price_cents=5000,  # $50.00 - 33% savings
        popular=False,
        savings_percent=33,
    ),
    TokenPackage(
        id="ultimate",
        name="Ultimate Pack",
        tokens=50000,
        price_cents=15000,  # $150.00 - 40% savings
        popular=False,
        savings_percent=40,
    ),
]

# Create a lookup dictionary for fast access
PACKAGE_LOOKUP: dict[str, TokenPackage] = {pkg.id: pkg for pkg in TOKEN_PACKAGES}


class StripeServiceError(Exception):
    """Base exception for Stripe service errors."""

    pass


class InvalidPackageError(StripeServiceError):
    """Raised when an invalid package ID is provided."""

    pass


class WebhookVerificationError(StripeServiceError):
    """Raised when webhook signature verification fails."""

    pass


class PaymentProcessingError(StripeServiceError):
    """Raised when payment processing fails."""

    pass


class StripeService:
    """Service for Stripe payment integration."""

    def __init__(self, db: AsyncSession):
        """Initialize Stripe service.

        Args:
            db: Database session for token operations
        """
        self.db = db
        self.token_service = TokenService(db)

    @staticmethod
    def get_packages() -> list[TokenPackage]:
        """Get all available token packages.

        Returns:
            List of TokenPackage objects
        """
        return TOKEN_PACKAGES.copy()

    @staticmethod
    def get_package(package_id: str) -> TokenPackage:
        """Get a specific token package by ID.

        Args:
            package_id: Package identifier

        Returns:
            TokenPackage object

        Raises:
            InvalidPackageError: If package ID is not found
        """
        package = PACKAGE_LOOKUP.get(package_id)
        if not package:
            raise InvalidPackageError(
                f"Invalid package ID: {package_id}. "
                f"Valid packages: {', '.join(PACKAGE_LOOKUP.keys())}"
            )
        return package

    async def create_checkout_session(
        self,
        user_id: int,
        package_id: str,
        success_url: str,
        cancel_url: str,
    ) -> tuple[str, str, int]:
        """Create a Stripe checkout session for token purchase.

        Args:
            user_id: User ID making the purchase
            package_id: Token package ID to purchase
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect if user cancels

        Returns:
            Tuple of (session_id, checkout_url, expires_at)

        Raises:
            InvalidPackageError: If package ID is invalid
            StripeServiceError: If checkout session creation fails
        """
        # Validate package
        package = self.get_package(package_id)

        logger.info(
            f"Creating checkout session for user {user_id}, "
            f"package {package_id} ({package.tokens} tokens, {package.price_display})"
        )

        try:
            # Create Stripe checkout session
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[
                    {
                        "price_data": {
                            "currency": package.currency,
                            "product_data": {
                                "name": package.name,
                                "description": f"{package.tokens:,} tokens for map generation",
                            },
                            "unit_amount": package.price_cents,
                        },
                        "quantity": 1,
                    }
                ],
                mode="payment",
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    "user_id": str(user_id),
                    "package_id": package_id,
                    "tokens": str(package.tokens),
                },
                client_reference_id=str(user_id),
                expires_at=None,  # Use Stripe's default expiration (24 hours)
            )

            logger.info(
                f"Checkout session created: {session.id} for user {user_id}"
            )

            return session.id, session.url, session.expires_at

        except stripe.error.StripeError as e:
            logger.error(f"Stripe API error creating checkout session: {e}")
            raise StripeServiceError(f"Failed to create checkout session: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error creating checkout session: {e}")
            raise StripeServiceError(f"Failed to create checkout session: {str(e)}")

    @staticmethod
    def verify_webhook_signature(
        payload: bytes,
        signature: str,
        webhook_secret: Optional[str] = None,
    ) -> stripe.Event:
        """Verify Stripe webhook signature and parse event.

        Args:
            payload: Raw webhook request body
            signature: Stripe-Signature header value
            webhook_secret: Optional webhook secret (defaults to settings)

        Returns:
            Verified Stripe Event object

        Raises:
            WebhookVerificationError: If signature verification fails
        """
        secret = webhook_secret or settings.STRIPE_WEBHOOK_SECRET

        if not secret:
            raise WebhookVerificationError(
                "STRIPE_WEBHOOK_SECRET not configured"
            )

        try:
            event = stripe.Webhook.construct_event(
                payload, signature, secret
            )
            logger.info(f"Webhook verified: {event['type']} ({event['id']})")
            return event

        except ValueError as e:
            # Invalid payload
            logger.error(f"Invalid webhook payload: {e}")
            raise WebhookVerificationError("Invalid webhook payload")
        except stripe.error.SignatureVerificationError as e:
            # Invalid signature
            logger.error(f"Invalid webhook signature: {e}")
            raise WebhookVerificationError("Invalid webhook signature")

    async def process_checkout_completed(
        self,
        event: stripe.Event,
    ) -> dict:
        """Process a checkout.session.completed webhook event.

        This is the primary webhook for handling successful payments.
        Tokens are granted to the user's balance.

        Args:
            event: Verified Stripe webhook event

        Returns:
            Dict with processing results

        Raises:
            PaymentProcessingError: If processing fails
        """
        session = event["data"]["object"]
        event_id = event["id"]

        # Extract metadata
        user_id = session.get("metadata", {}).get("user_id")
        package_id = session.get("metadata", {}).get("package_id")
        payment_status = session.get("payment_status")

        logger.info(
            f"Processing checkout.session.completed: "
            f"session={session['id']}, user={user_id}, package={package_id}, "
            f"status={payment_status}"
        )

        # Validate required fields
        if not user_id or not package_id:
            raise PaymentProcessingError(
                f"Missing metadata in session {session['id']}: "
                f"user_id={user_id}, package_id={package_id}"
            )

        # Verify payment status
        if payment_status != "paid":
            logger.warning(
                f"Checkout session {session['id']} status is '{payment_status}', "
                f"not 'paid'. Skipping token grant."
            )
            return {
                "success": False,
                "reason": f"Payment status is {payment_status}",
            }

        # Get package details
        try:
            package = self.get_package(package_id)
        except InvalidPackageError as e:
            raise PaymentProcessingError(str(e))

        # Check for duplicate processing (idempotency)
        # The stripe_event_id in Transaction table ensures we never double-grant
        try:
            new_balance = await self.token_service.add_tokens(
                user_id=int(user_id),
                amount=package.tokens,
                reason=TransactionType.PURCHASE,
                metadata={
                    "package_id": package_id,
                    "package_name": package.name,
                    "price_cents": package.price_cents,
                    "currency": package.currency,
                    "session_id": session["id"],
                    "customer_email": session.get("customer_details", {}).get("email"),
                },
                stripe_event_id=event_id,
            )

            logger.info(
                f"Granted {package.tokens} tokens to user {user_id}. "
                f"New balance: {new_balance}"
            )

            return {
                "success": True,
                "user_id": user_id,
                "tokens_granted": package.tokens,
                "new_balance": new_balance,
                "package": package_id,
            }

        except Exception as e:
            # Check if this is a duplicate event (constraint violation on stripe_event_id)
            error_msg = str(e).lower()
            if "unique constraint" in error_msg or "duplicate" in error_msg:
                logger.warning(
                    f"Duplicate webhook event {event_id} for user {user_id}, "
                    f"tokens already granted"
                )
                return {
                    "success": True,
                    "duplicate": True,
                    "message": "Tokens already granted for this payment",
                }

            # Other errors
            logger.error(f"Failed to grant tokens for event {event_id}: {e}")
            raise PaymentProcessingError(
                f"Failed to grant tokens: {str(e)}"
            )

    async def process_payment_intent_succeeded(
        self,
        event: stripe.Event,
    ) -> dict:
        """Process a payment_intent.succeeded webhook event.

        This is a supplementary webhook. The primary processing happens
        in checkout.session.completed. This logs the event for auditing.

        Args:
            event: Verified Stripe webhook event

        Returns:
            Dict with processing results
        """
        payment_intent = event["data"]["object"]
        event_id = event["id"]

        logger.info(
            f"Payment intent succeeded: {payment_intent['id']}, "
            f"amount={payment_intent['amount']} {payment_intent['currency']}"
        )

        # We don't grant tokens here - that happens in checkout.session.completed
        # This event is logged for auditing and monitoring
        return {
            "success": True,
            "event_type": "payment_intent.succeeded",
            "payment_intent_id": payment_intent["id"],
            "amount": payment_intent["amount"],
            "note": "Tokens granted via checkout.session.completed",
        }

    async def process_webhook_event(
        self,
        event: stripe.Event,
    ) -> dict:
        """Process a Stripe webhook event.

        Routes the event to the appropriate handler based on event type.

        Args:
            event: Verified Stripe webhook event

        Returns:
            Dict with processing results
        """
        event_type = event["type"]
        event_id = event["id"]

        logger.info(f"Processing webhook event: {event_type} ({event_id})")

        # Route to appropriate handler
        if event_type == "checkout.session.completed":
            return await self.process_checkout_completed(event)
        elif event_type == "payment_intent.succeeded":
            return await self.process_payment_intent_succeeded(event)
        elif event_type == "payment_intent.payment_failed":
            # Log payment failures for monitoring
            payment_intent = event["data"]["object"]
            logger.warning(
                f"Payment failed: {payment_intent['id']}, "
                f"error={payment_intent.get('last_payment_error')}"
            )
            return {"success": True, "event_type": event_type, "logged": True}
        elif event_type == "charge.refunded":
            # Handle refunds - this is a placeholder for future implementation
            # In production, you'd want to deduct tokens or mark them as refunded
            charge = event["data"]["object"]
            logger.warning(
                f"Charge refunded: {charge['id']}, amount={charge['amount_refunded']}"
            )
            return {"success": True, "event_type": event_type, "logged": True}
        else:
            # Unknown event type - log and ignore
            logger.info(f"Ignoring unhandled webhook event type: {event_type}")
            return {"success": True, "event_type": event_type, "ignored": True}


def get_stripe_service(db: AsyncSession) -> StripeService:
    """Factory function to create StripeService instance.

    Args:
        db: Database session

    Returns:
        Configured StripeService instance
    """
    return StripeService(db)
