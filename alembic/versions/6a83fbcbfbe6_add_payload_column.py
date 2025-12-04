"""add payload column

Revision ID: 6a83fbcbfbe6
Revises: 491171f5e93d
Create Date: 2025-12-04 22:25:54.532489

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6a83fbcbfbe6'
down_revision: Union[str, Sequence[str], None] = '491171f5e93d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('tasks', sa.Column('payload', sa.String(), nullable=False))
    pass


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('tasks', 'payload')
    pass
