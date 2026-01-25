"""OAuth2 provider implementations.

This module provides OAuth2 authentication with external providers:
- Google OAuth2
- GitHub OAuth2

Each provider implements the OAuthProvider protocol for consistent interface.
"""

import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class OAuthProvider(str, Enum):
    """Supported OAuth2 providers."""

    GOOGLE = "google"
    GITHUB = "github"


@dataclass
class OAuthUserInfo:
    """User information retrieved from OAuth provider.

    This is a normalized structure for user data from any OAuth provider.
    """

    provider: OAuthProvider
    provider_user_id: str  # Unique ID from the provider
    email: str
    name: Optional[str] = None
    picture_url: Optional[str] = None
    email_verified: bool = False


class OAuthError(Exception):
    """Base exception for OAuth errors."""

    pass


class OAuthConfigurationError(OAuthError):
    """Raised when OAuth provider is not properly configured."""

    pass


class OAuthTokenError(OAuthError):
    """Raised when token exchange fails."""

    pass


class OAuthUserInfoError(OAuthError):
    """Raised when fetching user info fails."""

    pass


class OAuthStateMismatchError(OAuthError):
    """Raised when OAuth state parameter doesn't match."""

    pass


class BaseOAuthProvider(ABC):
    """Abstract base class for OAuth2 providers.

    Defines the interface that all OAuth providers must implement.
    """

    @property
    @abstractmethod
    def provider_name(self) -> OAuthProvider:
        """Return the provider identifier."""
        pass

    @abstractmethod
    def get_authorization_url(self, state: str) -> str:
        """Generate the OAuth authorization URL.

        Args:
            state: CSRF protection state parameter

        Returns:
            Authorization URL to redirect user to
        """
        pass

    @abstractmethod
    async def exchange_code_for_token(self, code: str) -> str:
        """Exchange authorization code for access token.

        Args:
            code: Authorization code from callback

        Returns:
            Access token from provider

        Raises:
            OAuthTokenError: If token exchange fails
        """
        pass

    @abstractmethod
    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        """Fetch user information from the provider.

        Args:
            access_token: Valid access token

        Returns:
            Normalized user information

        Raises:
            OAuthUserInfoError: If fetching user info fails
        """
        pass

    async def authenticate(self, code: str) -> OAuthUserInfo:
        """Complete OAuth flow: exchange code and get user info.

        This is a convenience method that combines token exchange
        and user info retrieval.

        Args:
            code: Authorization code from callback

        Returns:
            Normalized user information

        Raises:
            OAuthTokenError: If token exchange fails
            OAuthUserInfoError: If fetching user info fails
        """
        access_token = await self.exchange_code_for_token(code)
        return await self.get_user_info(access_token)


def generate_oauth_state() -> str:
    """Generate a secure random state parameter for OAuth CSRF protection.

    Returns:
        32-character URL-safe random string
    """
    return secrets.token_urlsafe(24)


# Re-export providers for convenience
from app.services.oauth.github import GitHubOAuthProvider
from app.services.oauth.google import GoogleOAuthProvider

__all__ = [
    "OAuthProvider",
    "OAuthUserInfo",
    "OAuthError",
    "OAuthConfigurationError",
    "OAuthTokenError",
    "OAuthUserInfoError",
    "OAuthStateMismatchError",
    "BaseOAuthProvider",
    "GoogleOAuthProvider",
    "GitHubOAuthProvider",
    "generate_oauth_state",
]
