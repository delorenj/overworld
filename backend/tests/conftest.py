"""Pytest configuration and shared fixtures for backend tests."""

import os
import sys

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

# Add parent directory to path for app module discovery
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set test environment BEFORE importing app modules
os.environ.setdefault("ENVIRONMENT", "test")

from app.core.database import Base
from app.core.config import settings
from app.models.theme import Theme
from app.models.user import User


@pytest_asyncio.fixture
async def db_session():
    """Provide a test database session using PostgreSQL.

    Creates a fresh engine for each test to avoid event loop conflicts.
    Drops all tables, recreates them, runs the test, then drops again.
    This ensures test isolation.

    Note: Tests should be run inside Docker via `docker compose exec backend pytest`
    to ensure proper database connectivity.
    """
    # Create a fresh engine for this test (avoids event loop conflicts)
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        future=True,
        poolclass=NullPool,
    )

    session_factory = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    # Drop existing tables first to ensure clean state
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    # Create tables fresh
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Provide session
    async with session_factory() as session:
        yield session

    # Drop tables after test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    # Dispose engine
    await engine.dispose()


@pytest_asyncio.fixture
async def test_theme(db_session):
    """Create a test theme for map fixtures."""
    theme = Theme(
        name="Test Theme",
        description="A test theme for unit tests",
        is_premium=False,
        asset_manifest={"icons": [], "roads": [], "backgrounds": []},
    )
    db_session.add(theme)
    await db_session.commit()
    await db_session.refresh(theme)
    return theme


@pytest_asyncio.fixture
async def test_user(db_session):
    """Create a test user."""
    user = User(
        email="test@example.com",
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


# Configure pytest-asyncio
pytest_plugins = ["pytest_asyncio"]
