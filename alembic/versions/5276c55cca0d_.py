"""create the api_keys table

Revision ID: 5276c55cca0d
Revises: e78c1637c05c
Create Date: 2025-11-28 10:03:52.685688

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5276c55cca0d'
down_revision: Union[str, Sequence[str], None] = 'e78c1637c05c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('api_keys',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key_hash', sa.String(), nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='TRUE', nullable=False),
        sa.Column('expires_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('last_used_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key_hash')
    )
    pass


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('api_keys')
    pass
