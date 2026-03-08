"""Add linked_user_id to anonymous_usage for anon→account conversion.

Revision ID: 20260308_1615
Revises: 20260308_1538
Create Date: 2026-03-08 16:15:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = "20260308_1615"
down_revision: Union[str, None] = "20260308_1538"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "anonymous_usage",
        sa.Column("linked_user_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_anonymous_usage_linked_user_id_users",
        "anonymous_usage",
        "users",
        ["linked_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_anonymous_usage_linked_user_id",
        "anonymous_usage",
        ["linked_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_anonymous_usage_linked_user_id", table_name="anonymous_usage")
    op.drop_constraint(
        "fk_anonymous_usage_linked_user_id_users",
        "anonymous_usage",
        type_="foreignkey",
    )
    op.drop_column("anonymous_usage", "linked_user_id")
