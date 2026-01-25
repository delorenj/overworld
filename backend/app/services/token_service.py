"""Token service for managing user token balances and transactions.

This service provides business logic for:
- Getting user token balances
- Adding tokens (purchases, grants, refunds)
- Deducting tokens (generation costs)
- Tracking transaction history
- Estimating job costs based on document size
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.token_balance import TokenBalance
from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.models.document import Document

logger = logging.getLogger(__name__)

# Token cost constants
DEFAULT_STARTING_TOKENS = 100
TOKENS_PER_KB = 0.1  # 0.1 tokens per KB of document size
MIN_GENERATION_COST = 1  # Minimum cost for any generation
MAX_GENERATION_COST = 50  # Maximum cost cap
LOW_BALANCE_THRESHOLD = 10  # Warning threshold


class InsufficientTokensError(Exception):
    """Raised when user doesn't have enough tokens for an operation."""

    def __init__(self, required: int, available: int):
        self.required = required
        self.available = available
        super().__init__(
            f"Insufficient tokens: required {required}, available {available}"
        )


class TokenService:
    """Service for managing user token balances and transactions."""

    def __init__(self, db: AsyncSession):
        """Initialize the token service.

        Args:
            db: Database session for token operations
        """
        self.db = db

    async def get_balance(self, user_id: int) -> int:
        """Get the total token balance for a user.

        If the user doesn't have a TokenBalance record, one will be created
        with the default starting tokens.

        Args:
            user_id: The user's ID

        Returns:
            Total available tokens (free + purchased)
        """
        balance = await self._get_or_create_balance(user_id)
        return balance.total_tokens

    async def get_balance_details(self, user_id: int) -> dict:
        """Get detailed balance information for a user.

        Args:
            user_id: The user's ID

        Returns:
            Dict with free_tokens, purchased_tokens, total_tokens,
            last_reset_at, and is_low_balance
        """
        balance = await self._get_or_create_balance(user_id)
        return {
            "free_tokens": balance.free_tokens,
            "purchased_tokens": balance.purchased_tokens,
            "total_tokens": balance.total_tokens,
            "last_reset_at": balance.last_reset_at,
            "is_low_balance": balance.total_tokens <= LOW_BALANCE_THRESHOLD,
        }

    async def add_tokens(
        self,
        user_id: int,
        amount: int,
        reason: TransactionType,
        metadata: Optional[dict] = None,
        stripe_event_id: Optional[str] = None,
    ) -> int:
        """Add tokens to a user's balance.

        Args:
            user_id: The user's ID
            amount: Number of tokens to add (must be positive)
            reason: Type of transaction (PURCHASE, GRANT, REFUND, MONTHLY_RESET)
            metadata: Optional additional context for the transaction
            stripe_event_id: Optional Stripe event ID for purchases

        Returns:
            New total balance after addition

        Raises:
            ValueError: If amount is not positive or reason is GENERATION
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")

        if reason == TransactionType.GENERATION:
            raise ValueError("Use deduct_tokens for generation costs")

        balance = await self._get_or_create_balance(user_id)

        # Determine which pool to add to
        if reason == TransactionType.PURCHASE:
            balance.purchased_tokens += amount
        elif reason == TransactionType.MONTHLY_RESET:
            # Reset free tokens to the amount (typically default value)
            balance.free_tokens = amount
            balance.last_reset_at = datetime.now(timezone.utc)
        else:
            # Grants and refunds go to free tokens
            balance.free_tokens += amount

        # Create transaction record
        transaction = Transaction(
            user_id=user_id,
            type=reason,
            tokens_delta=amount,
            stripe_event_id=stripe_event_id,
            tx_metadata=metadata,
        )
        self.db.add(transaction)

        await self.db.commit()
        await self.db.refresh(balance)

        logger.info(
            f"Added {amount} tokens to user {user_id} ({reason.value}). "
            f"New balance: {balance.total_tokens}"
        )

        return balance.total_tokens

    async def deduct_tokens(
        self,
        user_id: int,
        amount: int,
        reason: str,
        metadata: Optional[dict] = None,
    ) -> bool:
        """Deduct tokens from a user's balance.

        Tokens are deducted from free tokens first, then purchased tokens.

        Args:
            user_id: The user's ID
            amount: Number of tokens to deduct (must be positive)
            reason: Description of what the tokens were used for
            metadata: Optional additional context (job_id, document_id, etc.)

        Returns:
            True if deduction was successful

        Raises:
            ValueError: If amount is not positive
            InsufficientTokensError: If user doesn't have enough tokens
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")

        balance = await self._get_or_create_balance(user_id)

        if balance.total_tokens < amount:
            raise InsufficientTokensError(
                required=amount,
                available=balance.total_tokens
            )

        # Deduct from free tokens first, then purchased
        remaining = amount
        if balance.free_tokens >= remaining:
            balance.free_tokens -= remaining
        else:
            remaining -= balance.free_tokens
            balance.free_tokens = 0
            balance.purchased_tokens -= remaining

        # Create transaction record with negative delta
        tx_metadata = metadata or {}
        tx_metadata["reason"] = reason
        transaction = Transaction(
            user_id=user_id,
            type=TransactionType.GENERATION,
            tokens_delta=-amount,
            tx_metadata=tx_metadata,
        )
        self.db.add(transaction)

        await self.db.commit()
        await self.db.refresh(balance)

        logger.info(
            f"Deducted {amount} tokens from user {user_id} ({reason}). "
            f"New balance: {balance.total_tokens}"
        )

        return True

    async def check_sufficient_balance(self, user_id: int, amount: int) -> bool:
        """Check if a user has sufficient balance for an operation.

        Args:
            user_id: The user's ID
            amount: Required token amount

        Returns:
            True if user has sufficient balance, False otherwise
        """
        balance = await self.get_balance(user_id)
        return balance >= amount

    async def get_transaction_history(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
        transaction_type: Optional[TransactionType] = None,
    ) -> tuple[list[Transaction], int]:
        """Get transaction history for a user.

        Args:
            user_id: The user's ID
            limit: Maximum number of transactions to return
            offset: Offset for pagination
            transaction_type: Optional filter by transaction type

        Returns:
            Tuple of (list of transactions, total count)
        """
        # Build base query
        base_query = select(Transaction).where(Transaction.user_id == user_id)

        if transaction_type:
            base_query = base_query.where(Transaction.type == transaction_type)

        # Get total count
        count_query = select(func.count()).select_from(base_query.subquery())
        total = await self.db.scalar(count_query) or 0

        # Get paginated results
        query = (
            base_query
            .order_by(Transaction.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(query)
        transactions = list(result.scalars().all())

        return transactions, total

    async def estimate_job_cost(
        self,
        document_id: Optional[str] = None,
        file_size_bytes: Optional[int] = None,
    ) -> dict:
        """Estimate the token cost for a generation job.

        Cost is calculated based on document size:
        - Base cost: MIN_GENERATION_COST tokens
        - Size factor: TOKENS_PER_KB per KB of document
        - Cap: MAX_GENERATION_COST tokens

        Args:
            document_id: Optional document ID to estimate cost for
            file_size_bytes: Optional direct file size in bytes

        Returns:
            Dict with estimated_cost, file_size_bytes, and breakdown
        """
        size_bytes = file_size_bytes

        # If document_id provided, look up the document
        if document_id and not size_bytes:
            from uuid import UUID
            try:
                doc_uuid = UUID(document_id)
                stmt = select(Document).where(Document.id == doc_uuid)
                result = await self.db.execute(stmt)
                document = result.scalar_one_or_none()
                if document:
                    size_bytes = document.file_size_bytes
            except (ValueError, Exception) as e:
                logger.warning(f"Could not look up document {document_id}: {e}")

        if not size_bytes:
            # Default estimate for unknown size
            return {
                "estimated_cost": MIN_GENERATION_COST,
                "file_size_bytes": None,
                "breakdown": {
                    "base_cost": MIN_GENERATION_COST,
                    "size_cost": 0,
                    "total": MIN_GENERATION_COST,
                },
            }

        # Calculate cost based on file size
        size_kb = size_bytes / 1024
        size_cost = int(size_kb * TOKENS_PER_KB)
        total_cost = min(MAX_GENERATION_COST, max(MIN_GENERATION_COST, size_cost))

        return {
            "estimated_cost": total_cost,
            "file_size_bytes": size_bytes,
            "breakdown": {
                "base_cost": MIN_GENERATION_COST,
                "size_cost": size_cost,
                "total": total_cost,
                "capped": total_cost == MAX_GENERATION_COST,
            },
        }

    async def refund_tokens(
        self,
        user_id: int,
        amount: int,
        reason: str,
        metadata: Optional[dict] = None,
    ) -> int:
        """Refund tokens to a user (e.g., for failed generation).

        Args:
            user_id: The user's ID
            amount: Number of tokens to refund
            reason: Reason for the refund
            metadata: Optional context (job_id, etc.)

        Returns:
            New total balance after refund
        """
        refund_metadata = metadata or {}
        refund_metadata["refund_reason"] = reason

        return await self.add_tokens(
            user_id=user_id,
            amount=amount,
            reason=TransactionType.REFUND,
            metadata=refund_metadata,
        )

    async def _get_or_create_balance(self, user_id: int) -> TokenBalance:
        """Get or create a TokenBalance record for a user.

        Args:
            user_id: The user's ID

        Returns:
            TokenBalance instance
        """
        stmt = select(TokenBalance).where(TokenBalance.user_id == user_id)
        result = await self.db.execute(stmt)
        balance = result.scalar_one_or_none()

        if balance is None:
            # Create new balance with default tokens
            balance = TokenBalance(
                user_id=user_id,
                free_tokens=DEFAULT_STARTING_TOKENS,
                purchased_tokens=0,
            )
            self.db.add(balance)
            await self.db.commit()
            await self.db.refresh(balance)

            # Record the initial grant
            transaction = Transaction(
                user_id=user_id,
                type=TransactionType.GRANT,
                tokens_delta=DEFAULT_STARTING_TOKENS,
                tx_metadata={"reason": "Initial token grant"},
            )
            self.db.add(transaction)
            await self.db.commit()

            logger.info(
                f"Created new token balance for user {user_id} "
                f"with {DEFAULT_STARTING_TOKENS} tokens"
            )

        return balance


def get_token_service(db: AsyncSession) -> TokenService:
    """Factory function to create TokenService.

    Args:
        db: Database session

    Returns:
        Configured TokenService instance
    """
    return TokenService(db)
