"""Add LATE and PERMISSION to attendance_status enum

Revision ID: 868fb447dd9e
Revises: 302bdfbcb204
Create Date: 2026-02-27 17:28:21.360624

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '868fb447dd9e'
down_revision: Union[str, None] = '302bdfbcb204'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add the new values to the Postgres Enum safely
    op.execute("ALTER TYPE attendance_status ADD VALUE IF NOT EXISTS 'LATE';")
    op.execute("ALTER TYPE attendance_status ADD VALUE IF NOT EXISTS 'PERMISSION';")

def downgrade() -> None:
    pass

