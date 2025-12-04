"""Adding new columns into the task database

Revision ID: 491171f5e93d
Revises: dff850017cc7
Create Date: 2025-12-04 15:29:53.620529

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '491171f5e93d'
down_revision: Union[str, Sequence[str], None] = 'dff850017cc7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add scheduled_at column
    op.add_column('tasks', sa.Column('scheduled_at', sa.TIMESTAMP(timezone=True), nullable=True))
    
    # Add retry_count column
    # We use server_default='0' so existing rows get filled with 0
    op.add_column('tasks', sa.Column('retry_count', sa.Integer(), server_default='0', nullable=True))


def downgrade() -> None:
    # Remove the columns if we rollback
    op.drop_column('tasks', 'retry_count')
    op.drop_column('tasks', 'scheduled_at')