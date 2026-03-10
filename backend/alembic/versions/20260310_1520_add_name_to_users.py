"""Add name column to users table for OAuth profile data.

Revision ID: 20260310_1520
Revises: 20260308_1615
Create Date: 2026-03-10 15:20:00.000000

Related: GitHub issue #6 - Get user first name from Google OAuth
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = "20260310_1520"
down_revision: Union[str, None] = "20260308_1615"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add name column to users table."""
    op.add_column(
        "users",
        sa.Column("name", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    """Remove name column from users table."""
    op.drop_column("users", "name")
