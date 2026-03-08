"""Add anonymous_usage table for free-tier session/IP tracking.

Revision ID: 20260308_1538
Revises: 20260225_0200
Create Date: 2026-03-08 15:38:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = "20260308_1538"
down_revision: Union[str, None] = "20260225_0200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "anonymous_usage",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("client_id_hash", sa.String(length=64), nullable=False),
        sa.Column("operation", sa.String(length=50), nullable=False),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("free_limit", sa.Integer(), nullable=False, server_default=sa.text("3")),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("window_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("client_id_hash", "operation", name="uq_anonymous_usage_client_op"),
    )

    op.create_index("ix_anonymous_usage_id", "anonymous_usage", ["id"], unique=False)
    op.create_index("ix_anonymous_usage_client_id_hash", "anonymous_usage", ["client_id_hash"], unique=False)
    op.create_index("ix_anonymous_usage_operation", "anonymous_usage", ["operation"], unique=False)
    op.create_index("ix_anonymous_usage_window_expires_at", "anonymous_usage", ["window_expires_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_anonymous_usage_window_expires_at", table_name="anonymous_usage")
    op.drop_index("ix_anonymous_usage_operation", table_name="anonymous_usage")
    op.drop_index("ix_anonymous_usage_client_id_hash", table_name="anonymous_usage")
    op.drop_index("ix_anonymous_usage_id", table_name="anonymous_usage")
    op.drop_table("anonymous_usage")
