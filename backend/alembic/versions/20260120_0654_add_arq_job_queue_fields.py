"""add ARQ job queue fields to generation_jobs

Revision ID: a1b2c3d4e5f6
Revises: 7a66a7d54df2
Create Date: 2026-01-20 06:54:00.000000

This migration adds fields required for ARQ-based job queue processing:
- arq_job_id: Unique ARQ job identifier
- progress_message: Human-readable progress status
- retry_count: Number of retry attempts
- max_retries: Maximum allowed retries
- next_retry_at: Scheduled retry timestamp
- error_code: Error classification for retry logic
- cancelled_at: Cancellation timestamp
- CANCELLED status to JobStatus enum
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "7a66a7d54df2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns to generation_jobs table
    op.add_column(
        "generation_jobs",
        sa.Column("arq_job_id", sa.String(255), nullable=True),
    )
    op.add_column(
        "generation_jobs",
        sa.Column("progress_message", sa.String(500), nullable=True),
    )
    op.add_column(
        "generation_jobs",
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "generation_jobs",
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
    )
    op.add_column(
        "generation_jobs",
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "generation_jobs",
        sa.Column("error_code", sa.String(50), nullable=True),
    )
    op.add_column(
        "generation_jobs",
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Note: document_id column already added in migration 7a66a7d54df2
    # No need to add it again

    # Create unique index on arq_job_id
    op.create_index(
        "ix_generation_jobs_arq_job_id",
        "generation_jobs",
        ["arq_job_id"],
        unique=True,
    )

    # Note: document_id index and FK already created in migration 7a66a7d54df2
    # No need to recreate them

    # Add CANCELLED to the jobstatus enum
    # PostgreSQL requires special handling for adding enum values
    op.execute("ALTER TYPE jobstatus ADD VALUE IF NOT EXISTS 'CANCELLED'")


def downgrade() -> None:
    # Note: Don't remove document_id FK/index - they belong to migration 7a66a7d54df2

    # Remove indexes
    op.drop_index("ix_generation_jobs_arq_job_id", table_name="generation_jobs")

    # Remove columns (excluding document_id)
    op.drop_column("generation_jobs", "cancelled_at")
    op.drop_column("generation_jobs", "error_code")
    op.drop_column("generation_jobs", "next_retry_at")
    op.drop_column("generation_jobs", "max_retries")
    op.drop_column("generation_jobs", "retry_count")
    op.drop_column("generation_jobs", "progress_message")
    op.drop_column("generation_jobs", "arq_job_id")

    # Note: Cannot easily remove enum value in PostgreSQL
    # The CANCELLED value will remain in the enum
