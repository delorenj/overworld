"""GitHub OAuth2 provider implementation.

Implements OAuth2 authentication flow with GitHub:
1. Generate authorization URL with required scopes
2. Exchange authorization code for access token
3. Fetch user profile and email information

GitHub OAuth2 Documentation:
https://docs.github.com/en/developers/apps/building-oauth-apps/authorizing-oauth-apps
"""

import logging
from typing import Optional
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

# GitHub OAuth2 endpoints
GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_EMAILS_URL = "https://api.github.com/user/emails"

# Required scopes for user info and email
GITHUB_SCOPES = [
    "read:user",
    "user:email",
]


class GitHubOAuthProvider(BaseOAuthProvider):
    """GitHub OAuth2 provider.

    Handles the complete OAuth2 flow with GitHub, including:
    - Authorization URL generation
    - Token exchange
    - User profile and email retrieval

    Note: GitHub may not return email in the main user endpoint if the
    user has set their email to private. We fetch from /user/emails as well.
    """

    def __init__(self) -> None:
        """Initialize GitHub OAuth provider.

        Raises:
            OAuthConfigurationError: If GitHub OAuth credentials are not configured
        """
        if not settings.GITHUB_CLIENT_ID or not settings.GITHUB_CLIENT_SECRET:
            raise OAuthConfigurationError(
                "GitHub OAuth2 is not configured. "
                "Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET environment variables."
            )

        self.client_id = settings.GITHUB_CLIENT_ID
        self.client_secret = settings.GITHUB_CLIENT_SECRET
        self.redirect_uri = f"{settings.OAUTH_REDIRECT_URL}/github/callback"

    @property
    def provider_name(self) -> OAuthProvider:
        """Return the provider identifier."""
        return OAuthProvider.GITHUB

    def get_authorization_url(self, state: str) -> str:
        """Generate GitHub OAuth authorization URL.

        Args:
            state: CSRF protection state parameter

        Returns:
            Authorization URL to redirect user to
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(GITHUB_SCOPES),
            "state": state,
            "allow_signup": "true",  # Allow new users to sign up via GitHub
        }

        url = f"{GITHUB_AUTH_URL}?{urlencode(params)}"
        logger.debug(f"Generated GitHub auth URL with redirect_uri: {self.redirect_uri}")
        return url

    async def exchange_code_for_token(self, code: str) -> str:
        """Exchange authorization code for access token.

        Args:
            code: Authorization code from callback

        Returns:
            Access token from GitHub

        Raises:
            OAuthTokenError: If token exchange fails
        """
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.redirect_uri,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    GITHUB_TOKEN_URL,
                    data=data,
                    headers={
                        "Accept": "application/json",  # Request JSON response
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    timeout=30.0,
                )

                if response.status_code != 200:
                    logger.error(f"GitHub token exchange failed with status {response.status_code}")
                    raise OAuthTokenError(f"Token exchange failed with status {response.status_code}")

                token_data = response.json()

                # Check for error in response
                if "error" in token_data:
                    error_msg = token_data.get("error_description", token_data["error"])
                    logger.error(f"GitHub token exchange error: {error_msg}")
                    raise OAuthTokenError(f"Failed to exchange code for token: {error_msg}")

                access_token = token_data.get("access_token")

                if not access_token:
                    raise OAuthTokenError("No access token in response")

                logger.info("Successfully exchanged GitHub auth code for token")
                return access_token

            except httpx.RequestError as e:
                logger.error(f"Network error during GitHub token exchange: {e}")
                raise OAuthTokenError(f"Network error: {e}")

    async def _get_primary_email(self, client: httpx.AsyncClient, access_token: str) -> Optional[str]:
        """Fetch primary email from GitHub emails endpoint.

        GitHub users can set their email to private, so we need to fetch
        from the dedicated emails endpoint.

        Args:
            client: HTTP client instance
            access_token: Valid GitHub access token

        Returns:
            Primary verified email or None
        """
        try:
            response = await client.get(
                GITHUB_EMAILS_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github.v3+json",
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                logger.warning(f"Failed to fetch GitHub emails: {response.status_code}")
                return None

            emails = response.json()

            # Find primary verified email
            for email_info in emails:
                if email_info.get("primary") and email_info.get("verified"):
                    return email_info.get("email")

            # Fall back to any verified email
            for email_info in emails:
                if email_info.get("verified"):
                    return email_info.get("email")

            return None

        except Exception as e:
            logger.warning(f"Error fetching GitHub emails: {e}")
            return None

    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        """Fetch user information from GitHub.

        Args:
            access_token: Valid GitHub access token

        Returns:
            Normalized user information

        Raises:
            OAuthUserInfoError: If fetching user info fails
        """
        async with httpx.AsyncClient() as client:
            try:
                # Fetch main user profile
                response = await client.get(
                    GITHUB_USER_URL,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/vnd.github.v3+json",
                    },
                    timeout=30.0,
                )

                if response.status_code != 200:
                    error_msg = f"Failed to fetch user info: status {response.status_code}"
                    logger.error(f"GitHub user info fetch failed: {error_msg}")
                    raise OAuthUserInfoError(error_msg)

                user_data = response.json()

                # Validate required fields
                github_id = user_data.get("id")
                if not github_id:
                    raise OAuthUserInfoError("No user ID in response")

                # Get email - try from profile first, then from emails endpoint
                email = user_data.get("email")
                email_verified = email is not None

                if not email:
                    # Fetch from emails endpoint for private email users
                    email = await self._get_primary_email(client, access_token)
                    email_verified = email is not None

                if not email:
                    raise OAuthUserInfoError(
                        "No email available. Please make sure your GitHub account "
                        "has a verified email address."
                    )

                user_info = OAuthUserInfo(
                    provider=OAuthProvider.GITHUB,
                    provider_user_id=str(github_id),
                    email=email.lower(),
                    name=user_data.get("name") or user_data.get("login"),
                    picture_url=user_data.get("avatar_url"),
                    email_verified=email_verified,
                )

                logger.info(f"Retrieved GitHub user info for: {user_info.email}")
                return user_info

            except httpx.RequestError as e:
                logger.error(f"Network error during GitHub user info fetch: {e}")
                raise OAuthUserInfoError(f"Network error: {e}")


def get_github_oauth_provider() -> GitHubOAuthProvider:
    """Factory function to create GitHubOAuthProvider instance.

    Returns:
        Configured GitHubOAuthProvider

    Raises:
        OAuthConfigurationError: If GitHub OAuth is not configured
    """
    return GitHubOAuthProvider()
