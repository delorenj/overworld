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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.transaction import TransactionType
from app.models.user import User
from app.schemas.stripe import TokenPackage, SubscriptionPlan
from app.services.token_service import TokenService

logger = logging.getLogger(__name__)

# Initialize Stripe with API key from settings
stripe.api_key = settings.STRIPE_SECRET_KEY

# Subscription Plans
SUBSCRIPTION_PLANS: list[SubscriptionPlan] = [
    SubscriptionPlan(
        id="campfire",
        name="Campfire",
        price_id=settings.STRIPE_PRICE_ID_CAMPFIRE or "price_campfire_placeholder",
        price_cents=2900,
        currency="usd",
        interval="month",
        features=["No watermarks", "Priority support", "Basic analytics"],
    ),
    SubscriptionPlan(
        id="guild",
        name="Guild",
        price_id=settings.STRIPE_PRICE_ID_GUILD or "price_guild_placeholder",
        price_cents=9900,
        currency="usd",
        interval="month",
        features=["All Campfire features", "Team seats (5)", "Advanced analytics"],
    ),
    SubscriptionPlan(
        id="studio_plus",
        name="Studio+",
        price_id=settings.STRIPE_PRICE_ID_STUDIO or "price_studio_plus_placeholder",
        price_cents=29900,
        currency="usd",
        interval="month",
        features=["All Guild features", "Unlimited seats", "SLA support"],
    ),
]
PLAN_LOOKUP: dict[str, SubscriptionPlan] = {plan.id: plan for plan in SUBSCRIPTION_PLANS}

# Token package definitions (configured via env-backed settings)
TOKEN_PACKAGES: list[TokenPackage] = [
    TokenPackage(
        id="starter",
        name="Starter Pack",
        tokens=settings.STRIPE_TOKEN_PACK_STARTER_TOKENS,
        price_cents=settings.STRIPE_TOKEN_PACK_STARTER_PRICE_CENTS,
        popular=False,
        savings_percent=0,
    ),
    TokenPackage(
        id="growth",
        name="Growth Pack",
        tokens=settings.STRIPE_TOKEN_PACK_GROWTH_TOKENS,
        price_cents=settings.STRIPE_TOKEN_PACK_GROWTH_PRICE_CENTS,
        popular=True,
        savings_percent=20,
    ),
    TokenPackage(
        id="scale",
        name="Scale Pack",
        tokens=settings.STRIPE_TOKEN_PACK_SCALE_TOKENS,
        price_cents=settings.STRIPE_TOKEN_PACK_SCALE_PRICE_CENTS,
        popular=False,
        savings_percent=30,
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
    def get_plans() -> list[SubscriptionPlan]:
        """Get all available subscription plans.

        Returns:
            List of SubscriptionPlan objects
        """
        return SUBSCRIPTION_PLANS.copy()

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

    @staticmethod
    def get_plan(plan_id: str) -> SubscriptionPlan:
        """Get a specific subscription plan by ID.

        Args:
            plan_id: Plan identifier

        Returns:
            SubscriptionPlan object

        Raises:
            InvalidPackageError: If plan ID is not found
        """
        plan = PLAN_LOOKUP.get(plan_id)
        if not plan:
            raise InvalidPackageError(
                f"Invalid plan ID: {plan_id}. "
                f"Valid plans: {', '.join(PLAN_LOOKUP.keys())}"
            )
        return plan

    async def create_checkout_session(
        self,
        user_id: Optional[int],
        package_id: str,
        success_url: str,
        cancel_url: str,
        anonymous_client_hash: Optional[str] = None,
        customer_email: Optional[str] = None,
    ) -> tuple[str, str, int]:
        """Create a Stripe checkout session for token purchase.

        Args:
            user_id: Optional user ID for authenticated checkout
            package_id: Token package ID to purchase
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect if user cancels
            anonymous_client_hash: Stable hash for anonymous session linkage
            customer_email: Optional customer email (required for anon checkout)

        Returns:
            Tuple of (session_id, checkout_url, expires_at)

        Raises:
            InvalidPackageError: If package ID is invalid
            StripeServiceError: If checkout session creation fails
        """
        package = self.get_package(package_id)

        if user_id is None and not anonymous_client_hash:
            raise StripeServiceError(
                "Anonymous checkout requires anonymous_client_hash"
            )

        metadata = {
            "package_id": package_id,
            "tokens": str(package.tokens),
            "checkout_origin": "authenticated" if user_id else "anonymous",
        }
        if user_id is not None:
            metadata["user_id"] = str(user_id)
        if anonymous_client_hash:
            metadata["anonymous_client_hash"] = anonymous_client_hash

        logger.info(
            "Creating checkout session",
            extra={
                "user_id": user_id,
                "package_id": package_id,
                "anonymous": user_id is None,
            },
        )

        try:
            checkout_params = {
                "payment_method_types": ["card"],
                "line_items": [
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
                "mode": "payment",
                "success_url": success_url,
                "cancel_url": cancel_url,
                "metadata": metadata,
            }

            if user_id is not None:
                checkout_params["client_reference_id"] = str(user_id)
            else:
                checkout_params["customer_creation"] = "always"

            if customer_email:
                checkout_params["customer_email"] = customer_email

            session = stripe.checkout.Session.create(**checkout_params)

            logger.info(
                f"Checkout session created: {session.id} for "
                f"{'user ' + str(user_id) if user_id else 'anonymous checkout'}"
            )

            return session.id, session.url, session.expires_at

        except stripe.error.StripeError as e:
            logger.error(f"Stripe API error creating checkout session: {e}")
            raise StripeServiceError(f"Failed to create checkout session: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error creating checkout session: {e}")
            raise StripeServiceError(f"Failed to create checkout session: {str(e)}")

    async def create_subscription_session(
        self,
        user_id: int,
        plan_id: str,
        success_url: str,
        cancel_url: str,
    ) -> tuple[str, str, int]:
        """Create a Stripe checkout session for subscription.

        Args:
            user_id: User ID subscribing
            plan_id: Subscription plan ID
            success_url: Success redirect URL
            cancel_url: Cancel redirect URL

        Returns:
            Tuple of (session_id, checkout_url, expires_at)
        """
        plan = self.get_plan(plan_id)

        logger.info(
            f"Creating subscription session for user {user_id}, "
            f"plan {plan_id} (${plan.price_cents/100:.2f})"
        )

        try:
            # Create Stripe subscription checkout session
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[
                    {
                        "price": plan.price_id,
                        "quantity": 1,
                    }
                ],
                mode="subscription",
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    "user_id": str(user_id),
                    "plan_id": plan.id,
                    "type": "subscription",
                },
                subscription_data={
                    "metadata": {
                        "user_id": str(user_id),
                        "plan_id": plan.id,
                    }
                },
                client_reference_id=str(user_id),
            )

            logger.info(
                f"Subscription session created: {session.id} for user {user_id}"
            )

            return session.id, session.url, session.expires_at

        except stripe.error.StripeError as e:
            logger.error(f"Stripe API error creating subscription session: {e}")
            raise StripeServiceError(f"Failed to create subscription session: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error creating subscription session: {e}")
            raise StripeServiceError(f"Failed to create subscription session: {str(e)}")

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

        Handles both token purchases and subscription signups.

        Args:
            event: Verified Stripe webhook event

        Returns:
            Dict with processing results

        Raises:
            PaymentProcessingError: If processing fails
        """
        session = event["data"]["object"]
        event_id = event["id"]

        metadata = session.get("metadata", {})
        package_id = metadata.get("package_id")
        plan_id = metadata.get("plan_id")
        payment_status = session.get("payment_status")
        checkout_type = metadata.get("type", "token_purchase")

        # Resolve user from explicit metadata or anonymous email conversion flow
        user_id, user_created = await self._resolve_checkout_user(
            metadata=metadata,
            session=session,
        )
        anonymous_client_hash = metadata.get("anonymous_client_hash")

        logger.info(
            f"Processing checkout.session.completed: "
            f"session={session['id']}, user={user_id}, type={checkout_type}, "
            f"status={payment_status}, created={user_created}"
        )

        # Handle subscription checkout
        if checkout_type == "subscription":
            if payment_status != "paid":
                logger.warning(
                    f"Subscription checkout {session['id']} status is '{payment_status}'. "
                    f"Skipping activation."
                )
                return {"success": False, "reason": "Payment not paid"}
            
            # Update user is_premium status
            from app.models.user import User
            from sqlalchemy import update
            
            stmt = update(User).where(User.id == int(user_id)).values(is_premium=True)
            await self.db.execute(stmt)
            await self.db.commit()
            
            logger.info(f"Activated premium status for user {user_id} (Plan: {plan_id})")
            return {
                "success": True, 
                "user_id": user_id, 
                "type": "subscription", 
                "plan": plan_id,
                "activated": True
            }

        # Handle token purchase (existing logic)
        if not package_id:
            raise PaymentProcessingError(
                f"Missing package_id in session {session['id']}"
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
            if anonymous_client_hash:
                await self.token_service.link_anonymous_session_to_user(
                    client_id_hash=anonymous_client_hash,
                    user_id=int(user_id),
                )

            new_balance = await self.token_service.credit_tokens(
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
                    "anonymous_client_hash": anonymous_client_hash,
                    "converted_account_created": user_created,
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
                "account_created": user_created,
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

    async def _resolve_checkout_user(
        self,
        metadata: dict,
        session: dict,
    ) -> tuple[int, bool]:
        """Resolve user for checkout completion.

        Returns:
            tuple[user_id, user_created]
        """
        explicit_user_id = metadata.get("user_id")
        if explicit_user_id:
            try:
                return int(explicit_user_id), False
            except (TypeError, ValueError) as exc:
                raise PaymentProcessingError(
                    f"Invalid user_id in session {session.get('id')}"
                ) from exc

        customer_email = (
            session.get("customer_details", {}).get("email")
            or session.get("customer_email")
        )
        if not customer_email:
            raise PaymentProcessingError(
                f"Anonymous checkout {session.get('id')} missing customer email"
            )

        normalized_email = customer_email.lower().strip()
        user_stmt = select(User).where(User.email == normalized_email)
        user_result = await self.db.execute(user_stmt)
        user = user_result.scalar_one_or_none()

        if user:
            return user.id, False

        user = User(
            email=normalized_email,
            password_hash=None,
            is_verified=True,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        logger.info(
            f"Created user {user.id} from anonymous Stripe checkout ({normalized_email})"
        )
        return user.id, True

    async def process_subscription_event(
        self,
        event: stripe.Event,
    ) -> dict:
        """Process customer.subscription.* webhook events."""
        subscription = event["data"]["object"]
        event_type = event["type"]
        event_id = event["id"]
        
        user_id = subscription.get("metadata", {}).get("user_id")
        plan_id = subscription.get("metadata", {}).get("plan_id")
        status = subscription.get("status")

        logger.info(
            f"Processing subscription event: {event_type}, user={user_id}, "
            f"plan={plan_id}, status={status}"
        )

        if not user_id:
            logger.warning(f"Subscription event {event_id} missing user_id metadata")
            return {"success": False, "reason": "Missing user_id"}

        # Logic to update user premium status based on subscription status
        # active, trialing => premium
        # past_due, unpaid, canceled, incomplete, incomplete_expired => not premium
        
        is_premium = status in ["active", "trialing"]
        
        from app.models.user import User
        from sqlalchemy import update
        
        stmt = update(User).where(User.id == int(user_id)).values(is_premium=is_premium)
        await self.db.execute(stmt)
        await self.db.commit()
        
        logger.info(f"Updated user {user_id} premium status to {is_premium} (status={status})")
        
        return {
            "success": True,
            "user_id": user_id,
            "event": event_type,
            "status": status,
            "is_premium": is_premium
        }

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
        elif event_type.startswith("customer.subscription."):
            return await self.process_subscription_event(event)
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
