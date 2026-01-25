"""Unit tests for token service.

Tests cover:
- Balance retrieval and auto-creation
- Token addition (purchases, grants, refunds)
- Token deduction (generation costs)
- Insufficient balance handling
- Transaction history
- Cost estimation
"""

import pytest
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4

from app.core.database import Base, get_engine, get_session_factory
from app.models import User, TokenBalance, Transaction
from app.models.transaction import TransactionType
from app.models.document import Document, DocumentStatus
from app.services.token_service import (
    TokenService,
    InsufficientTokensError,
    get_token_service,
    DEFAULT_STARTING_TOKENS,
    MIN_GENERATION_COST,
    MAX_GENERATION_COST,
    TOKENS_PER_KB,
    LOW_BALANCE_THRESHOLD,
)


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


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        email="testuser@example.com",
        password_hash="hashed_password",
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_user_with_balance(db_session: AsyncSession) -> User:
    """Create a test user with existing token balance."""
    user = User(
        email="userbalance@example.com",
        password_hash="hashed_password",
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    balance = TokenBalance(
        user_id=user.id,
        free_tokens=50,
        purchased_tokens=100,
    )
    db_session.add(balance)
    await db_session.commit()

    return user


@pytest.fixture
def token_service(db_session: AsyncSession) -> TokenService:
    """Provide a token service instance."""
    return get_token_service(db_session)


# ============================================================================
# Balance Retrieval Tests
# ============================================================================

@pytest.mark.asyncio
async def test_get_balance_creates_new_balance(
    token_service: TokenService,
    test_user: User,
):
    """Test that get_balance creates a new balance for users without one."""
    balance = await token_service.get_balance(test_user.id)

    assert balance == DEFAULT_STARTING_TOKENS


@pytest.mark.asyncio
async def test_get_balance_returns_existing_balance(
    token_service: TokenService,
    test_user_with_balance: User,
):
    """Test that get_balance returns existing balance."""
    balance = await token_service.get_balance(test_user_with_balance.id)

    # 50 free + 100 purchased = 150 total
    assert balance == 150


@pytest.mark.asyncio
async def test_get_balance_details(
    token_service: TokenService,
    test_user_with_balance: User,
):
    """Test get_balance_details returns all balance info."""
    details = await token_service.get_balance_details(test_user_with_balance.id)

    assert details["free_tokens"] == 50
    assert details["purchased_tokens"] == 100
    assert details["total_tokens"] == 150
    assert details["is_low_balance"] is False
    assert "last_reset_at" in details


@pytest.mark.asyncio
async def test_low_balance_detection(
    db_session: AsyncSession,
    test_user: User,
):
    """Test that low balance is correctly detected."""
    # Create balance below threshold
    balance = TokenBalance(
        user_id=test_user.id,
        free_tokens=5,
        purchased_tokens=3,
    )
    db_session.add(balance)
    await db_session.commit()

    service = get_token_service(db_session)
    details = await service.get_balance_details(test_user.id)

    assert details["total_tokens"] == 8
    assert details["is_low_balance"] is True


# ============================================================================
# Token Addition Tests
# ============================================================================

@pytest.mark.asyncio
async def test_add_tokens_purchase(
    token_service: TokenService,
    test_user_with_balance: User,
    db_session: AsyncSession,
):
    """Test adding tokens via purchase."""
    new_balance = await token_service.add_tokens(
        user_id=test_user_with_balance.id,
        amount=50,
        reason=TransactionType.PURCHASE,
        metadata={"stripe_payment_id": "pi_123"},
    )

    # 150 original + 50 = 200
    assert new_balance == 200

    # Verify purchased tokens increased
    result = await db_session.execute(
        select(TokenBalance).where(TokenBalance.user_id == test_user_with_balance.id)
    )
    balance = result.scalar_one()
    assert balance.purchased_tokens == 150  # 100 + 50


@pytest.mark.asyncio
async def test_add_tokens_grant(
    token_service: TokenService,
    test_user_with_balance: User,
    db_session: AsyncSession,
):
    """Test adding tokens via grant."""
    new_balance = await token_service.add_tokens(
        user_id=test_user_with_balance.id,
        amount=25,
        reason=TransactionType.GRANT,
        metadata={"reason": "Promotional bonus"},
    )

    # 150 original + 25 = 175
    assert new_balance == 175

    # Verify free tokens increased (grants go to free)
    result = await db_session.execute(
        select(TokenBalance).where(TokenBalance.user_id == test_user_with_balance.id)
    )
    balance = result.scalar_one()
    assert balance.free_tokens == 75  # 50 + 25


@pytest.mark.asyncio
async def test_add_tokens_monthly_reset(
    token_service: TokenService,
    test_user_with_balance: User,
    db_session: AsyncSession,
):
    """Test monthly token reset."""
    new_balance = await token_service.add_tokens(
        user_id=test_user_with_balance.id,
        amount=10,  # Reset to 10 free tokens
        reason=TransactionType.MONTHLY_RESET,
    )

    # Free tokens reset to 10, purchased stays at 100
    assert new_balance == 110

    result = await db_session.execute(
        select(TokenBalance).where(TokenBalance.user_id == test_user_with_balance.id)
    )
    balance = result.scalar_one()
    assert balance.free_tokens == 10
    assert balance.purchased_tokens == 100


@pytest.mark.asyncio
async def test_add_tokens_creates_transaction(
    token_service: TokenService,
    test_user_with_balance: User,
    db_session: AsyncSession,
):
    """Test that adding tokens creates a transaction record."""
    await token_service.add_tokens(
        user_id=test_user_with_balance.id,
        amount=30,
        reason=TransactionType.PURCHASE,
    )

    result = await db_session.execute(
        select(Transaction)
        .where(Transaction.user_id == test_user_with_balance.id)
        .where(Transaction.type == TransactionType.PURCHASE)
    )
    tx = result.scalar_one()

    assert tx.tokens_delta == 30
    assert tx.type == TransactionType.PURCHASE


@pytest.mark.asyncio
async def test_add_tokens_invalid_amount(
    token_service: TokenService,
    test_user: User,
):
    """Test that adding zero or negative tokens raises error."""
    with pytest.raises(ValueError, match="Amount must be positive"):
        await token_service.add_tokens(
            user_id=test_user.id,
            amount=0,
            reason=TransactionType.GRANT,
        )

    with pytest.raises(ValueError, match="Amount must be positive"):
        await token_service.add_tokens(
            user_id=test_user.id,
            amount=-10,
            reason=TransactionType.GRANT,
        )


@pytest.mark.asyncio
async def test_add_tokens_generation_type_not_allowed(
    token_service: TokenService,
    test_user: User,
):
    """Test that using GENERATION type for add_tokens raises error."""
    with pytest.raises(ValueError, match="Use deduct_tokens for generation costs"):
        await token_service.add_tokens(
            user_id=test_user.id,
            amount=10,
            reason=TransactionType.GENERATION,
        )


# ============================================================================
# Token Deduction Tests
# ============================================================================

@pytest.mark.asyncio
async def test_deduct_tokens_from_free_first(
    token_service: TokenService,
    test_user_with_balance: User,
    db_session: AsyncSession,
):
    """Test that tokens are deducted from free tokens first."""
    success = await token_service.deduct_tokens(
        user_id=test_user_with_balance.id,
        amount=30,
        reason="Map generation",
    )

    assert success is True

    result = await db_session.execute(
        select(TokenBalance).where(TokenBalance.user_id == test_user_with_balance.id)
    )
    balance = result.scalar_one()

    # Free tokens should go from 50 to 20
    assert balance.free_tokens == 20
    # Purchased tokens should remain at 100
    assert balance.purchased_tokens == 100


@pytest.mark.asyncio
async def test_deduct_tokens_overflow_to_purchased(
    token_service: TokenService,
    test_user_with_balance: User,
    db_session: AsyncSession,
):
    """Test that excess deduction overflows to purchased tokens."""
    # Deduct 70 tokens (50 free + 20 from purchased)
    success = await token_service.deduct_tokens(
        user_id=test_user_with_balance.id,
        amount=70,
        reason="Large map generation",
    )

    assert success is True

    result = await db_session.execute(
        select(TokenBalance).where(TokenBalance.user_id == test_user_with_balance.id)
    )
    balance = result.scalar_one()

    # Free tokens should be 0
    assert balance.free_tokens == 0
    # Purchased should be 100 - 20 = 80
    assert balance.purchased_tokens == 80


@pytest.mark.asyncio
async def test_deduct_tokens_creates_negative_transaction(
    token_service: TokenService,
    test_user_with_balance: User,
    db_session: AsyncSession,
):
    """Test that deducting tokens creates a transaction with negative delta."""
    await token_service.deduct_tokens(
        user_id=test_user_with_balance.id,
        amount=15,
        reason="Map generation",
        metadata={"job_id": 123},
    )

    result = await db_session.execute(
        select(Transaction)
        .where(Transaction.user_id == test_user_with_balance.id)
        .where(Transaction.type == TransactionType.GENERATION)
    )
    tx = result.scalar_one()

    assert tx.tokens_delta == -15
    assert tx.type == TransactionType.GENERATION
    assert tx.tx_metadata["job_id"] == 123


@pytest.mark.asyncio
async def test_deduct_tokens_insufficient_balance(
    token_service: TokenService,
    test_user_with_balance: User,
):
    """Test that deducting more than available raises InsufficientTokensError."""
    # User has 150 tokens, try to deduct 200
    with pytest.raises(InsufficientTokensError) as exc_info:
        await token_service.deduct_tokens(
            user_id=test_user_with_balance.id,
            amount=200,
            reason="Large map generation",
        )

    assert exc_info.value.required == 200
    assert exc_info.value.available == 150


@pytest.mark.asyncio
async def test_deduct_tokens_invalid_amount(
    token_service: TokenService,
    test_user: User,
):
    """Test that deducting zero or negative tokens raises error."""
    with pytest.raises(ValueError, match="Amount must be positive"):
        await token_service.deduct_tokens(
            user_id=test_user.id,
            amount=0,
            reason="Test",
        )


# ============================================================================
# Balance Check Tests
# ============================================================================

@pytest.mark.asyncio
async def test_check_sufficient_balance_true(
    token_service: TokenService,
    test_user_with_balance: User,
):
    """Test check_sufficient_balance returns True when sufficient."""
    result = await token_service.check_sufficient_balance(
        user_id=test_user_with_balance.id,
        amount=100,
    )
    assert result is True


@pytest.mark.asyncio
async def test_check_sufficient_balance_false(
    token_service: TokenService,
    test_user_with_balance: User,
):
    """Test check_sufficient_balance returns False when insufficient."""
    result = await token_service.check_sufficient_balance(
        user_id=test_user_with_balance.id,
        amount=200,
    )
    assert result is False


# ============================================================================
# Transaction History Tests
# ============================================================================

@pytest.mark.asyncio
async def test_get_transaction_history(
    token_service: TokenService,
    test_user_with_balance: User,
    db_session: AsyncSession,
):
    """Test retrieving transaction history."""
    # Create some transactions
    for i in range(5):
        tx = Transaction(
            user_id=test_user_with_balance.id,
            type=TransactionType.GENERATION,
            tokens_delta=-1,
            tx_metadata={"job_id": i},
        )
        db_session.add(tx)

    tx_grant = Transaction(
        user_id=test_user_with_balance.id,
        type=TransactionType.GRANT,
        tokens_delta=10,
    )
    db_session.add(tx_grant)
    await db_session.commit()

    transactions, total = await token_service.get_transaction_history(
        user_id=test_user_with_balance.id,
    )

    assert total == 6
    assert len(transactions) == 6


@pytest.mark.asyncio
async def test_get_transaction_history_with_filter(
    token_service: TokenService,
    test_user_with_balance: User,
    db_session: AsyncSession,
):
    """Test filtering transaction history by type."""
    # Create mixed transactions
    for i in range(3):
        tx = Transaction(
            user_id=test_user_with_balance.id,
            type=TransactionType.GENERATION,
            tokens_delta=-1,
        )
        db_session.add(tx)

    for i in range(2):
        tx = Transaction(
            user_id=test_user_with_balance.id,
            type=TransactionType.GRANT,
            tokens_delta=10,
        )
        db_session.add(tx)

    await db_session.commit()

    # Filter by GENERATION only
    transactions, total = await token_service.get_transaction_history(
        user_id=test_user_with_balance.id,
        transaction_type=TransactionType.GENERATION,
    )

    assert total == 3
    assert all(tx.type == TransactionType.GENERATION for tx in transactions)


@pytest.mark.asyncio
async def test_get_transaction_history_pagination(
    token_service: TokenService,
    test_user_with_balance: User,
    db_session: AsyncSession,
):
    """Test transaction history pagination."""
    # Create 15 transactions
    for i in range(15):
        tx = Transaction(
            user_id=test_user_with_balance.id,
            type=TransactionType.GENERATION,
            tokens_delta=-1,
        )
        db_session.add(tx)
    await db_session.commit()

    # Get first page
    page1, total = await token_service.get_transaction_history(
        user_id=test_user_with_balance.id,
        limit=10,
        offset=0,
    )

    assert total == 15
    assert len(page1) == 10

    # Get second page
    page2, _ = await token_service.get_transaction_history(
        user_id=test_user_with_balance.id,
        limit=10,
        offset=10,
    )

    assert len(page2) == 5


# ============================================================================
# Cost Estimation Tests
# ============================================================================

@pytest.mark.asyncio
async def test_estimate_job_cost_minimum(
    token_service: TokenService,
):
    """Test cost estimation returns minimum cost for small files."""
    estimate = await token_service.estimate_job_cost(file_size_bytes=100)

    assert estimate["estimated_cost"] == MIN_GENERATION_COST
    assert estimate["breakdown"]["base_cost"] == MIN_GENERATION_COST


@pytest.mark.asyncio
async def test_estimate_job_cost_based_on_size(
    token_service: TokenService,
):
    """Test cost scales with file size."""
    # 100KB file at 0.1 tokens/KB = 10 tokens
    estimate = await token_service.estimate_job_cost(file_size_bytes=100 * 1024)

    assert estimate["estimated_cost"] == 10
    assert estimate["file_size_bytes"] == 100 * 1024


@pytest.mark.asyncio
async def test_estimate_job_cost_maximum_cap(
    token_service: TokenService,
):
    """Test cost is capped at maximum."""
    # 1MB file would be 100 tokens, but capped at MAX
    estimate = await token_service.estimate_job_cost(file_size_bytes=1024 * 1024)

    assert estimate["estimated_cost"] == MAX_GENERATION_COST
    assert estimate["breakdown"]["capped"] is True


@pytest.mark.asyncio
async def test_estimate_job_cost_from_document(
    token_service: TokenService,
    test_user: User,
    db_session: AsyncSession,
):
    """Test cost estimation from document ID."""
    # Create a document
    doc = Document(
        id=uuid4(),
        user_id=test_user.id,
        filename="test.md",
        file_size_bytes=50 * 1024,  # 50KB
        mime_type="text/markdown",
        r2_path="documents/test.md",
        r2_url="https://example.com/test.md",
        status=DocumentStatus.PROCESSED,
    )
    db_session.add(doc)
    await db_session.commit()

    estimate = await token_service.estimate_job_cost(document_id=str(doc.id))

    # 50KB at 0.1 tokens/KB = 5 tokens
    assert estimate["estimated_cost"] == 5
    assert estimate["file_size_bytes"] == 50 * 1024


@pytest.mark.asyncio
async def test_estimate_job_cost_unknown_document(
    token_service: TokenService,
):
    """Test cost estimation with unknown document returns minimum."""
    estimate = await token_service.estimate_job_cost(
        document_id=str(uuid4())
    )

    assert estimate["estimated_cost"] == MIN_GENERATION_COST
    assert estimate["file_size_bytes"] is None


# ============================================================================
# Refund Tests
# ============================================================================

@pytest.mark.asyncio
async def test_refund_tokens(
    token_service: TokenService,
    test_user_with_balance: User,
    db_session: AsyncSession,
):
    """Test refunding tokens for failed generation."""
    new_balance = await token_service.refund_tokens(
        user_id=test_user_with_balance.id,
        amount=10,
        reason="Generation failed",
        metadata={"job_id": 456},
    )

    # 150 + 10 = 160
    assert new_balance == 160

    # Verify transaction
    result = await db_session.execute(
        select(Transaction)
        .where(Transaction.user_id == test_user_with_balance.id)
        .where(Transaction.type == TransactionType.REFUND)
    )
    tx = result.scalar_one()

    assert tx.tokens_delta == 10
    assert tx.tx_metadata["refund_reason"] == "Generation failed"


# ============================================================================
# Auto-Creation Tests
# ============================================================================

@pytest.mark.asyncio
async def test_auto_create_balance_records_initial_grant(
    token_service: TokenService,
    test_user: User,
    db_session: AsyncSession,
):
    """Test that auto-creating balance also creates initial grant transaction."""
    # Trigger balance creation
    await token_service.get_balance(test_user.id)

    # Check for grant transaction
    result = await db_session.execute(
        select(Transaction)
        .where(Transaction.user_id == test_user.id)
        .where(Transaction.type == TransactionType.GRANT)
    )
    tx = result.scalar_one()

    assert tx.tokens_delta == DEFAULT_STARTING_TOKENS
    assert tx.tx_metadata["reason"] == "Initial token grant"


# ============================================================================
# Factory Function Test
# ============================================================================

@pytest.mark.asyncio
async def test_get_token_service_factory(db_session: AsyncSession):
    """Test the factory function creates a valid service."""
    service = get_token_service(db_session)

    assert isinstance(service, TokenService)
    assert service.db is db_session
