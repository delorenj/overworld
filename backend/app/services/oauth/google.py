"""Google OAuth2 provider implementation.

Implements OAuth2 authentication flow with Google:
1. Generate authorization URL with required scopes
2. Exchange authorization code for access token
3. Fetch user profile information

Google OAuth2 Documentation:
https://developers.google.com/identity/protocols/oauth2/web-server
"""

import logging
from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.services.oauth import (
    BaseOAuthProvider,
    OAuthConfigurationError,
    OAuthProvider,
    OAuthTokenError,
    OAuthUserInfo,
    OAuthUserInfoError,
)

logger = logging.getLogger(__name__)

# Google OAuth2 endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

# Required scopes for user info
GOOGLE_SCOPES = [
    "openid",
    "email",
    "profile",
]


class GoogleOAuthProvider(BaseOAuthProvider):
    """Google OAuth2 provider.

    Handles the complete OAuth2 flow with Google, including:
    - Authorization URL generation
    - Token exchange
    - User profile retrieval
    """

    def __init__(self) -> None:
        """Initialize Google OAuth provider.

        Raises:
            OAuthConfigurationError: If Google OAuth credentials are not configured
        """
        if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
            raise OAuthConfigurationError(
                "Google OAuth2 is not configured. "
                "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables."
            )

        self.client_id = settings.GOOGLE_CLIENT_ID
        self.client_secret = settings.GOOGLE_CLIENT_SECRET
        self.redirect_uri = f"{settings.OAUTH_REDIRECT_URL}/google/callback"

    @property
    def provider_name(self) -> OAuthProvider:
        """Return the provider identifier."""
        return OAuthProvider.GOOGLE

    def get_authorization_url(self, state: str) -> str:
        """Generate Google OAuth authorization URL.

        Args:
            state: CSRF protection state parameter

        Returns:
            Authorization URL to redirect user to
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(GOOGLE_SCOPES),
            "state": state,
            "access_type": "offline",  # Request refresh token
            "prompt": "consent",  # Always show consent screen for refresh token
        }

        url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
        logger.debug(f"Generated Google auth URL with redirect_uri: {self.redirect_uri}")
        return url

    async def exchange_code_for_token(self, code: str) -> str:
        """Exchange authorization code for access token.

        Args:
            code: Authorization code from callback

        Returns:
            Access token from Google

        Raises:
            OAuthTokenError: If token exchange fails
        """
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    GOOGLE_TOKEN_URL,
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=30.0,
                )

                if response.status_code != 200:
                    error_data = response.json()
                    error_msg = error_data.get("error_description", error_data.get("error", "Unknown error"))
                    logger.error(f"Google token exchange failed: {error_msg}")
                    raise OAuthTokenError(f"Failed to exchange code for token: {error_msg}")

                token_data = response.json()
                access_token = token_data.get("access_token")

                if not access_token:
                    raise OAuthTokenError("No access token in response")

                logger.info("Successfully exchanged Google auth code for token")
                return access_token

            except httpx.RequestError as e:
                logger.error(f"Network error during Google token exchange: {e}")
                raise OAuthTokenError(f"Network error: {e}")

    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        """Fetch user information from Google.

        Args:
            access_token: Valid Google access token

        Returns:
            Normalized user information

        Raises:
            OAuthUserInfoError: If fetching user info fails
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    GOOGLE_USERINFO_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=30.0,
                )

                if response.status_code != 200:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("message", "Unknown error")
                    logger.error(f"Google user info fetch failed: {error_msg}")
                    raise OAuthUserInfoError(f"Failed to fetch user info: {error_msg}")

                user_data = response.json()

                # Validate required fields
                google_id = user_data.get("id")
                email = user_data.get("email")

                if not google_id:
                    raise OAuthUserInfoError("No user ID in response")
                if not email:
                    raise OAuthUserInfoError("No email in response")

                user_info = OAuthUserInfo(
                    provider=OAuthProvider.GOOGLE,
                    provider_user_id=str(google_id),
                    email=email.lower(),
                    name=user_data.get("name"),
                    picture_url=user_data.get("picture"),
                    email_verified=user_data.get("verified_email", False),
                )

                logger.info(f"Retrieved Google user info for: {user_info.email}")
                return user_info

            except httpx.RequestError as e:
                logger.error(f"Network error during Google user info fetch: {e}")
                raise OAuthUserInfoError(f"Network error: {e}")


def get_google_oauth_provider() -> GoogleOAuthProvider:
    """Factory function to create GoogleOAuthProvider instance.

    Returns:
        Configured GoogleOAuthProvider

    Raises:
        OAuthConfigurationError: If Google OAuth is not configured
    """
    return GoogleOAuthProvider()
