"""Application configuration using Pydantic settings."""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment
    ENVIRONMENT: Literal["development", "staging", "production", "test"] = "development"

    # Database
    DATABASE_URL: str = (
        "postgresql+asyncpg://overworld:overworld_dev_password@postgres:5432/overworld"
    )

    # Redis
    REDIS_URL: str = "redis://:overworld_redis_password@redis:6379/0"
    REDIS_MAX_CONNECTIONS: int = 50

    # RabbitMQ
    RABBITMQ_URL: str = "amqp://overworld:overworld_rabbitmq_password@rabbitmq:5672/"

    # JWT
    JWT_SECRET_KEY: str = "dev_jwt_secret_change_in_production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # External Services
    OPENROUTER_API_KEY: str = ""

    # Stripe Payment Integration
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    # Anonymous User Rate Limiting
    ANONYMOUS_DAILY_LIMIT: int = 3  # Free map generations per day for anonymous users

    # Cloudflare R2
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_ENDPOINT_URL: str = ""
    R2_BUCKET_NAME: str = "overworld"  # Single bucket for MVP
    # Separate buckets for future use
    R2_BUCKET_UPLOADS: str = "overworld"
    R2_BUCKET_MAPS: str = "overworld"
    R2_BUCKET_THEMES: str = "overworld"
    R2_BUCKET_EXPORTS: str = "overworld"

    # API
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "Overworld"
    VERSION: str = "0.1.0"

    # OAuth2 - Google
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # OAuth2 - GitHub
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""

    # OAuth2 - Common
    OAUTH_REDIRECT_URL: str = "http://localhost:8000/api/v1/auth"  # Base URL for callbacks


# Global settings instance
settings = Settings()
