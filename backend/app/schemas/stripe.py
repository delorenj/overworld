"""Pydantic schemas for Stripe payment integration.

This module defines request and response models for:
- Token package definitions
- Checkout session creation
- Webhook event processing
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field, HttpUrl


class TokenPackage(BaseModel):
    """Token package available for purchase."""

    id: str = Field(description="Package identifier")
    name: str = Field(description="Human-readable package name")
    tokens: int = Field(ge=1, description="Number of tokens included")
    price_cents: int = Field(ge=0, description="Price in cents (USD)")
    currency: str = Field(default="usd", description="ISO currency code")
    popular: bool = Field(default=False, description="Mark as popular/recommended")
    savings_percent: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
        description="Percentage savings compared to base rate"
    )

    @property
    def price_display(self) -> str:
        """Format price for display (e.g., $5.00)."""
        dollars = self.price_cents / 100
        return f"${dollars:.2f}"

    @property
    def price_per_token(self) -> float:
        """Calculate price per token in cents."""
        return self.price_cents / self.tokens

    class Config:
        json_schema_extra = {
            "example": {
                "id": "starter",
                "name": "Starter Pack",
                "tokens": 1000,
                "price_cents": 500,
                "currency": "usd",
                "popular": False,
                "savings_percent": 0,
            }
        }


class CheckoutRequest(BaseModel):
    """Request to create a Stripe checkout session."""

    package_id: str = Field(description="Token package ID to purchase")
    success_url: HttpUrl = Field(
        description="URL to redirect to after successful payment"
    )
    cancel_url: HttpUrl = Field(
        description="URL to redirect to if user cancels"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "package_id": "starter",
                "success_url": "https://example.com/payment/success",
                "cancel_url": "https://example.com/payment/cancel",
            }
        }


class CheckoutResponse(BaseModel):
    """Response containing Stripe checkout session details."""

    session_id: str = Field(description="Stripe checkout session ID")
    checkout_url: HttpUrl = Field(description="URL to redirect user to Stripe checkout")
    expires_at: int = Field(description="Unix timestamp when session expires")

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "cs_test_123456789",
                "checkout_url": "https://checkout.stripe.com/c/pay/cs_test_123456789",
                "expires_at": 1704067200,
            }
        }


class TokenPackagesResponse(BaseModel):
    """Response containing all available token packages."""

    packages: list[TokenPackage] = Field(description="Available token packages")
    currency: str = Field(default="usd", description="Currency for all packages")


class WebhookEvent(BaseModel):
    """Internal representation of a Stripe webhook event.

    This is used internally for processing, not for external API.
    """

    event_id: str = Field(description="Stripe event ID (for idempotency)")
    event_type: Literal[
        "checkout.session.completed",
        "payment_intent.succeeded",
        "payment_intent.payment_failed",
        "charge.refunded",
    ] = Field(description="Type of webhook event")
    user_id: Optional[int] = Field(
        default=None,
        description="User ID from session metadata"
    )
    package_id: Optional[str] = Field(
        default=None,
        description="Package ID from session metadata"
    )
    amount_total: int = Field(ge=0, description="Total amount in cents")
    currency: str = Field(description="Payment currency")
    payment_status: str = Field(description="Payment status from Stripe")
    session_id: Optional[str] = Field(
        default=None,
        description="Checkout session ID"
    )
    customer_email: Optional[str] = Field(
        default=None,
        description="Customer email from Stripe"
    )


class PaymentStatusResponse(BaseModel):
    """Response for payment status check."""

    session_id: str = Field(description="Checkout session ID")
    status: Literal["pending", "processing", "completed", "failed", "expired"] = Field(
        description="Current payment status"
    )
    tokens_granted: Optional[int] = Field(
        default=None,
        description="Tokens granted if payment completed"
    )
    amount_paid: Optional[int] = Field(
        default=None,
        description="Amount paid in cents"
    )
