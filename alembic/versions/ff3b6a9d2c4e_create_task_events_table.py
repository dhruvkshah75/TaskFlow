"""create task_events table

Revision ID: ff3b6a9d2c4e
Revises: 8af25adf8e4d
Create Date: 2025-12-09 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'ff3b6a9d2c4e'
down_revision: Union[str, Sequence[str], None] = '8af25adf8e4d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create task_events table and ensure Postgres enum exists.

    This migration creates a Postgres enum type `eventtype` if it does not
    already exist, then creates the `task_events` table which uses that enum.
    Creating the enum is guarded with a DO block so running the migration on
    a database that already has the enum will not raise an error.
    """

    # Create the enum type only if it doesn't already exist (guarded)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'eventtype') THEN
                CREATE TYPE eventtype AS ENUM (
                    'CREATED', 'QUEUED', 'PICKED_UP', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'RETRIED'
                );
            END IF;
        END$$;
        """
    )

    event_enum = postgresql.ENUM(
        'CREATED', 'QUEUED', 'PICKED_UP', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'RETRIED',
        name='eventtype', create_type=False
    )

    op.create_table(
        'task_events',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('task_id', sa.Integer(), sa.ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_type', event_enum, nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    )


def downgrade() -> None:
    """Drop the `task_events` table.

    We intentionally do not drop the `eventtype` enum here because other
    migrations or tables may rely on it; dropping global enum types can cause
    errors during downgrades if other objects still reference them.
    """

    op.drop_table('task_events')
