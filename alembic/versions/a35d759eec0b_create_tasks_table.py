"""create tasks table

Revision ID: a35d759eec0b
Revises: d9b244e43d98
Create Date: 2025-12-06 02:26:27.790091

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a35d759eec0b'
down_revision: Union[str, Sequence[str], None] = 'd9b244e43d98'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use postgres ENUM object and create it explicitly
    task_status = postgresql.ENUM(
        'PENDING', 'IN_PROGRESS', 'QUEUED', 'COMPLETED', 'FAILED', 'RETRYING',
        name='taskstatus'
    )
    priority_type = postgresql.ENUM('low', 'high', name='prioritytype')

    # create enum types if they don't exist
    task_status.create(op.get_bind(), checkfirst=True)
    priority_type.create(op.get_bind(), checkfirst=True)

    # In the table, use an Enum with create_type=False so SQLAlchemy won't try to create it again
    op.create_table(
        'tasks',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('payload', sa.String(), nullable=False),
        sa.Column('priority',
                  postgresql.ENUM('low', 'high', name='prioritytype', create_type=False),
                  nullable=False,
                  server_default=sa.text("'low'")),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.Column('status',
                  postgresql.ENUM(
                      'PENDING', 'IN_PROGRESS', 'QUEUED', 'COMPLETED', 'FAILED', 'RETRYING',
                      name='taskstatus', create_type=False),
                  nullable=False,
                  server_default=sa.text("'PENDING'")),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('worker_id', sa.String(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('scheduled_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
    )




def downgrade() -> None:
    """Downgrade schema."""
    # Drop tables first (dependents)
    op.drop_table('tasks')

    # Drop ENUM types
    priority_type = sa.Enum(name='prioritytype')
    task_status = sa.Enum(name='taskstatus')

    # use drop with checkfirst to avoid errors if types are absent
    priority_type.drop(op.get_bind(), checkfirst=True)
    task_status.drop(op.get_bind(), checkfirst=True)
