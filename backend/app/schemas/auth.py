"""Pydantic schemas for authentication endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserRegisterRequest(BaseModel):
    """Schema for user registration request."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="User password (min 8 characters)",
    )

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password has minimum strength requirements."""
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserLoginRequest(BaseModel):
    """Schema for user login request."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class TokenResponse(BaseModel):
    """Schema for token response (access + refresh tokens)."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type (always 'bearer')")
    expires_in: int = Field(..., description="Access token expiration time in seconds")


class TokenRefreshRequest(BaseModel):
    """Schema for token refresh request."""

    refresh_token: str = Field(..., description="JWT refresh token to exchange")


class UserResponse(BaseModel):
    """Schema for user information response."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="User ID")
    email: str = Field(..., description="User email address")
    is_verified: bool = Field(..., description="Whether user email is verified")
    is_premium: bool = Field(..., description="Whether user has premium subscription")
    created_at: datetime = Field(..., description="Account creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")


class AuthMessageResponse(BaseModel):
    """Schema for simple message responses."""

    message: str = Field(..., description="Response message")


class TokenPayload(BaseModel):
    """Schema for JWT token payload (internal use)."""

    sub: str = Field(..., description="Subject (user ID)")
    type: str = Field(..., description="Token type ('access' or 'refresh')")
    exp: int = Field(..., description="Expiration timestamp")
    iat: int = Field(..., description="Issued at timestamp")


# =============================================================================
# OAuth2 Schemas
# =============================================================================


class OAuthLoginResponse(BaseModel):
    """Schema for OAuth login initiation response.

    Contains the authorization URL to redirect the user to.
    """

    authorization_url: str = Field(..., description="OAuth provider authorization URL")
    state: str = Field(
        ...,
        description="State parameter for CSRF protection (store this for validation)",
    )


class OAuthCallbackRequest(BaseModel):
    """Schema for OAuth callback query parameters.

    Note: These are typically query params, but we validate them as a schema.
    """

    code: str = Field(..., description="Authorization code from OAuth provider")
    state: str = Field(..., description="State parameter for CSRF validation")
    error: Optional[str] = Field(None, description="Error code from OAuth provider")
    error_description: Optional[str] = Field(
        None, description="Error description from OAuth provider"
    )
