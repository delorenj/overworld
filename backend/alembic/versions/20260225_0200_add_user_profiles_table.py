"""Add user_profiles table for preferences and history.

Revision ID: a1b2c3d4e5f6
Revises: (auto-detected)
Create Date: 2026-02-25 02:00:00.000000

Related: OWRLD-20, Holyfields overworld/user_profile.v1.json
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = "20260225_0200"
down_revision: Union[str, None] = "9e408895f93a"  # Depends on project/consensus analysis migration
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        # Display preferences
        sa.Column(
            "default_theme_id",
            sa.Integer(),
            sa.ForeignKey("themes.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "default_map_visibility",
            sa.String(20),
            nullable=False,
            server_default="private",
        ),
        sa.Column(
            "color_mode", sa.String(20), nullable=False, server_default="system"
        ),
        sa.Column(
            "language", sa.String(10), nullable=False, server_default="en"
        ),
        # Notification preferences
        sa.Column(
            "notifications_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "email_marketing",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        # Map defaults
        sa.Column(
            "auto_watermark",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        # History counters
        sa.Column(
            "total_maps_created",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "total_exports",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Index on user_id for fast lookups
    op.create_index("ix_user_profiles_user_id", "user_profiles", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_profiles_user_id", table_name="user_profiles")
    op.drop_table("user_profiles")
