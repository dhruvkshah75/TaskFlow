"""add index on tasks

Revision ID: 8af25adf8e4d
Revises: a35d759eec0b
Create Date: 2025-12-06 02:58:13.039029

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8af25adf8e4d'
down_revision: Union[str, Sequence[str], None] = 'a35d759eec0b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_index(
        "ix_tasks_status_scheduled_at",
        "tasks",
        ["status", "scheduled_at"]
    )

def downgrade():
    op.drop_index("ix_tasks_status_scheduled_at", table_name="tasks")
