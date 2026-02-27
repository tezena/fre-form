"""Add is_active to attendance_sessions

Revision ID: 0dcd095c54dd
Revises: 868fb447dd9e
Create Date: 2026-02-27 18:18:08.716242

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0dcd095c54dd'
down_revision: Union[str, None] = '868fb447dd9e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Safely add the column and set existing rows to True
    op.add_column(
        'attendance_sessions', 
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False)
    )


def downgrade() -> None:
    # Remove the column if we ever need to rollback
    op.drop_column('attendance_sessions', 'is_active')