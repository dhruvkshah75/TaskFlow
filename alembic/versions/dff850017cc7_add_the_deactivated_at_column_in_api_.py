"""Add the deactivated_at column in api-keys table

Revision ID: dff850017cc7
Revises: 5276c55cca0d
Create Date: 2025-12-01 23:46:42.875868

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dff850017cc7'
down_revision: Union[str, Sequence[str], None] = '5276c55cca0d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('api_keys', sa.Column(
        'deactivated_at', 
        sa.TIMESTAMP(timezone=True), 
        nullable=True
        )
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('api_keys', 'deactivated_at')
