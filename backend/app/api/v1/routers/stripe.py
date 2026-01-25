"""API routes for Stripe payment integration.

This module provides REST endpoints for:
- GET /api/v1/stripe/packages - List available token packages
- POST /api/v1/stripe/checkout - Create checkout session
- POST /api/v1/stripe/webhook - Handle Stripe webhooks
- GET /api/v1/stripe/config - Get public Stripe configuration
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.user import User
from app.schemas.stripe import (
    CheckoutRequest,
    CheckoutResponse,
    TokenPackage,
    TokenPackagesResponse,
)
from app.services.stripe_service import (
    StripeService,
    get_stripe_service,
    InvalidPackageError,
    StripeServiceError,
    WebhookVerificationError,
    PaymentProcessingError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stripe", tags=["stripe", "payments"])


@router.get(
    "/packages",
    response_model=TokenPackagesResponse,
    summary="List token packages",
    description="Get all available token packages for purchase",
)
async def list_packages() -> TokenPackagesResponse:
    """List all available token packages.

    Returns package details including:
    - Token amounts
    - Prices in cents
    - Savings percentages
    - Popular flags

    No authentication required - packages are public information.

    Returns:
        TokenPackagesResponse with all available packages
    """
    packages = StripeService.get_packages()
    return TokenPackagesResponse(packages=packages, currency="usd")


@router.get(
    "/config",
    response_model=dict,
    summary="Get Stripe configuration",
    description="Get public Stripe configuration (publishable key)",
)
async def get_stripe_config() -> dict:
    """Get public Stripe configuration.

    Returns the publishable key needed for Stripe.js integration
    on the frontend.

    Returns:
        Dict with publishable_key
    """
    if not settings.STRIPE_PUBLISHABLE_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe is not configured",
        )

    return {
        "publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
    }


@router.post(
    "/checkout",
    response_model=CheckoutResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create checkout session",
    description="Create a Stripe checkout session for token purchase",
)
async def create_checkout_session(
    request: CheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CheckoutResponse:
    """Create a Stripe checkout session for token purchase.

    This endpoint creates a Stripe checkout session and returns the
    checkout URL where the user should be redirected to complete payment.

    The checkout session includes:
    - Selected token package
    - User metadata for webhook processing
    - Success/cancel redirect URLs

    Args:
        request: Checkout request with package_id and redirect URLs
        current_user: Authenticated user
        db: Database session

    Returns:
        CheckoutResponse with session_id and checkout_url

    Raises:
        HTTPException(400): If package_id is invalid
        HTTPException(503): If Stripe is not configured or unavailable
    """
    stripe_service = get_stripe_service(db)

    try:
        session_id, checkout_url, expires_at = await stripe_service.create_checkout_session(
            user_id=current_user.id,
            package_id=request.package_id,
            success_url=str(request.success_url),
            cancel_url=str(request.cancel_url),
        )

        logger.info(
            f"Checkout session created for user {current_user.id}: {session_id}"
        )

        return CheckoutResponse(
            session_id=session_id,
            checkout_url=checkout_url,
            expires_at=expires_at,
        )

    except InvalidPackageError as e:
        logger.warning(f"Invalid package request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except StripeServiceError as e:
        logger.error(f"Stripe service error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment service temporarily unavailable",
        )


@router.post(
    "/webhook",
    status_code=status.HTTP_200_OK,
    summary="Stripe webhook handler",
    description="Handle Stripe webhook events (signature verified)",
    include_in_schema=False,  # Hide from public API docs
)
async def handle_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Handle Stripe webhook events.

    This endpoint receives webhook events from Stripe and processes them.
    It verifies the webhook signature for security and handles different
    event types:

    - checkout.session.completed: Grant tokens after successful payment
    - payment_intent.succeeded: Log successful payment
    - payment_intent.payment_failed: Log failed payment
    - charge.refunded: Log refund (future: deduct tokens)

    IMPORTANT: This endpoint must be accessible without authentication
    as it's called by Stripe's servers. Security is provided by webhook
    signature verification.

    Args:
        request: FastAPI request with raw body and signature header
        db: Database session

    Returns:
        Dict with processing status

    Raises:
        HTTPException(400): If signature verification fails
        HTTPException(500): If webhook processing fails
    """
    # Get raw request body for signature verification
    try:
        payload = await request.body()
    except Exception as e:
        logger.error(f"Failed to read webhook payload: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid request body",
        )

    # Get Stripe signature from headers
    signature = request.headers.get("Stripe-Signature")
    if not signature:
        logger.warning("Webhook request missing Stripe-Signature header")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe signature",
        )

    # Verify webhook signature and parse event
    stripe_service = get_stripe_service(db)

    try:
        event = StripeService.verify_webhook_signature(
            payload=payload,
            signature=signature,
        )
    except WebhookVerificationError as e:
        logger.error(f"Webhook verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook signature",
        )

    # Process the webhook event
    try:
        result = await stripe_service.process_webhook_event(event)

        logger.info(
            f"Webhook processed successfully: {event['type']} ({event['id']})"
        )

        return {
            "success": True,
            "event_id": event["id"],
            "event_type": event["type"],
            "result": result,
        }

    except PaymentProcessingError as e:
        logger.error(f"Payment processing error: {e}")
        # Return 500 so Stripe retries the webhook
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process webhook",
        )
    except Exception as e:
        logger.error(f"Unexpected webhook processing error: {e}")
        # Return 500 so Stripe retries the webhook
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process webhook",
        )


@router.get(
    "/packages/{package_id}",
    response_model=TokenPackage,
    summary="Get package details",
    description="Get details for a specific token package",
)
async def get_package(package_id: str) -> TokenPackage:
    """Get details for a specific token package.

    Args:
        package_id: Package identifier (e.g., "starter", "pro")

    Returns:
        TokenPackage details

    Raises:
        HTTPException(404): If package_id is not found
    """
    try:
        package = StripeService.get_package(package_id)
        return package
    except InvalidPackageError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
