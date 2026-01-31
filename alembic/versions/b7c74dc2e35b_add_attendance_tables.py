"""add_attendance_tables

Revision ID: b7c74dc2e35b
Revises: e3bcb3eed1c9
Create Date: 2026-01-31 18:15:42.809270

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c74dc2e35b'
down_revision: Union[str, None] = 'e3bcb3eed1c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Create ENUM types on Postgres
    if dialect == "postgresql":
        op.execute("CREATE TYPE program_type AS ENUM ('REGULAR', 'EVENT')")
        op.execute("CREATE TYPE attendance_type AS ENUM ('REGULAR', 'EVENT')")

    # Create programs table
    op.create_table(
        'programs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('department_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.Enum('REGULAR', 'EVENT', name='program_type'), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['department_id'], ['departments.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create attendance_sessions table
    op.create_table(
        'attendance_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('department_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.Enum('REGULAR', 'EVENT', name='attendance_type'), nullable=True),
        sa.Column('target_category', sa.String(), nullable=False),
        sa.Column('program_id', sa.Integer(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['department_id'], ['departments.id'], ),
        sa.ForeignKeyConstraint(['program_id'], ['programs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create attendance_records table
    op.create_table(
        'attendance_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('present', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('notes', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['attendance_sessions.id'], ),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Drop tables in reverse order
    op.drop_table('attendance_records')
    op.drop_table('attendance_sessions')
    op.drop_table('programs')

    # Drop ENUM types on Postgres
    if dialect == "postgresql":
        op.execute("DROP TYPE IF EXISTS attendance_type")
        op.execute("DROP TYPE IF EXISTS program_type")

