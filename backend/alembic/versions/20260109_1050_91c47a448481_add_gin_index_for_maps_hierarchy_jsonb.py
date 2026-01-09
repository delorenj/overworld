"""add GIN index for maps hierarchy JSONB

Revision ID: 91c47a448481
Revises: cf9a1d378cb5
Create Date: 2026-01-09 10:50:52.411386

"""
from collections.abc import Sequence
from typing import Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '91c47a448481'
down_revision: Union[str, None] = 'cf9a1d378cb5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create GIN index on maps.hierarchy for fast JSONB queries
    op.create_index(
        'idx_maps_hierarchy_gin',
        'maps',
        ['hierarchy'],
        unique=False,
        postgresql_using='gin',
    )


def downgrade() -> None:
    op.drop_index('idx_maps_hierarchy_gin', table_name='maps')
