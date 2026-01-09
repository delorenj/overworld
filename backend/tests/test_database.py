"""Database connectivity and model tests."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base, get_engine, get_session_factory
from app.models import GenerationJob, Map, Theme, TokenBalance, Transaction, User


@pytest.fixture
async def db_session():
    """Provide a test database session."""
    engine = get_engine()
    session_factory = get_session_factory()

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Provide session
    async with session_factory() as session:
        yield session

    # Drop tables after test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_database_connection(db_session: AsyncSession):
    """Test basic database connectivity."""
    result = await db_session.execute(select(1))
    assert result.scalar() == 1


@pytest.mark.asyncio
async def test_user_model_crud(db_session: AsyncSession):
    """Test User model CRUD operations."""
    # Create
    user = User(
        email="test@example.com",
        password_hash="hashed_password",
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    assert user.id is not None
    assert user.email == "test@example.com"
    assert user.is_verified is True

    # Read
    result = await db_session.execute(select(User).where(User.email == "test@example.com"))
    found_user = result.scalar_one()
    assert found_user.id == user.id

    # Update
    user.is_premium = True
    await db_session.commit()
    await db_session.refresh(user)
    assert user.is_premium is True

    # Delete
    await db_session.delete(user)
    await db_session.commit()

    result = await db_session.execute(select(User).where(User.id == user.id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_user_token_balance_relationship(db_session: AsyncSession):
    """Test User -> TokenBalance relationship."""
    # Create user
    user = User(email="test@example.com", is_verified=True)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create token balance
    balance = TokenBalance(
        user_id=user.id,
        free_tokens=10,
        purchased_tokens=50,
    )
    db_session.add(balance)
    await db_session.commit()

    # Verify relationship
    result = await db_session.execute(
        select(User).where(User.id == user.id)
    )
    user = result.scalar_one()

    # Access relationship
    assert user.token_balance.free_tokens == 10
    assert user.token_balance.purchased_tokens == 50
    assert user.token_balance.total_tokens == 60


@pytest.mark.asyncio
async def test_cascade_delete(db_session: AsyncSession):
    """Test cascade delete for user and related records."""
    # Create user with related records
    user = User(email="test@example.com", is_verified=True)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Add token balance
    balance = TokenBalance(user_id=user.id)
    db_session.add(balance)

    # Add transaction
    transaction = Transaction(
        user_id=user.id,
        type="GRANT",
        tokens_delta=10,
    )
    db_session.add(transaction)

    await db_session.commit()

    # Delete user (should cascade delete token_balance and transactions)
    await db_session.delete(user)
    await db_session.commit()

    # Verify cascading deletes
    balance_result = await db_session.execute(
        select(TokenBalance).where(TokenBalance.user_id == user.id)
    )
    assert balance_result.scalar_one_or_none() is None

    tx_result = await db_session.execute(
        select(Transaction).where(Transaction.user_id == user.id)
    )
    assert tx_result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_jsonb_storage(db_session: AsyncSession):
    """Test JSONB column storage and retrieval."""
    # Create theme with JSONB asset_manifest
    theme = Theme(
        name="SMB3",
        description="Super Mario Bros 3 style",
        is_premium=False,
        asset_manifest={
            "colors": {"road": "#D2691E", "bg": "#6B8CFF"},
            "textures": {"road": "pixelated-brown"},
            "icons": ["mushroom", "star", "coin"],
        },
    )
    db_session.add(theme)
    await db_session.commit()
    await db_session.refresh(theme)

    # Verify JSONB data
    assert theme.asset_manifest["colors"]["road"] == "#D2691E"
    assert "mushroom" in theme.asset_manifest["icons"]


@pytest.mark.asyncio
async def test_enum_storage(db_session: AsyncSession):
    """Test Enum column storage."""
    user = User(email="test@example.com", is_verified=True)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create transaction with enum type
    transaction = Transaction(
        user_id=user.id,
        type="GENERATION",
        tokens_delta=-1,
    )
    db_session.add(transaction)
    await db_session.commit()
    await db_session.refresh(transaction)

    # Verify enum
    assert transaction.type == "GENERATION"
    assert transaction.tokens_delta == -1
