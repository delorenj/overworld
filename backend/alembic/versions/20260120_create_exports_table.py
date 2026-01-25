"""Create exports table

Revision ID: 20260120_exports
Revises: 20260120_0654_add_arq_job_queue_fields
Create Date: 2026-01-20 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260120_exports'
down_revision = '20260120_0654_add_arq_job_queue_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create exports table for map exports."""
    # Create export_format enum
    op.execute("CREATE TYPE exportformat AS ENUM ('png', 'svg')")

    # Create export_status enum
    op.execute("CREATE TYPE exportstatus AS ENUM ('pending', 'processing', 'completed', 'failed')")

    # Create exports table
    op.create_table(
        'exports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('map_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('format', postgresql.ENUM('png', 'svg', name='exportformat', create_type=False), nullable=False),
        sa.Column('resolution', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('status', postgresql.ENUM('pending', 'processing', 'completed', 'failed', name='exportstatus', create_type=False), nullable=False, server_default='pending'),
        sa.Column('file_path', sa.String(length=512), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('watermarked', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('error_message', sa.String(length=1024), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['map_id'], ['maps.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index(op.f('ix_exports_id'), 'exports', ['id'], unique=False)
    op.create_index(op.f('ix_exports_map_id'), 'exports', ['map_id'], unique=False)
    op.create_index(op.f('ix_exports_user_id'), 'exports', ['user_id'], unique=False)
    op.create_index(op.f('ix_exports_status'), 'exports', ['status'], unique=False)
    op.create_index(op.f('ix_exports_created_at'), 'exports', ['created_at'], unique=False)
    op.create_index(op.f('ix_exports_expires_at'), 'exports', ['expires_at'], unique=False)


def downgrade() -> None:
    """Drop exports table."""
    op.drop_index(op.f('ix_exports_expires_at'), table_name='exports')
    op.drop_index(op.f('ix_exports_created_at'), table_name='exports')
    op.drop_index(op.f('ix_exports_status'), table_name='exports')
    op.drop_index(op.f('ix_exports_user_id'), table_name='exports')
    op.drop_index(op.f('ix_exports_map_id'), table_name='exports')
    op.drop_index(op.f('ix_exports_id'), table_name='exports')
    op.drop_table('exports')

    # Drop enums
    op.execute('DROP TYPE exportstatus')
    op.execute('DROP TYPE exportformat')
