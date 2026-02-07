"""create_attendance_tables_fresh

Revision ID: e04950fcf918
Revises: e3bcb3eed1c9
Create Date: 2026-02-07 13:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e04950fcf918'
down_revision: Union[str, None] = 'e3bcb3eed1c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---------------------------------------------------------
    # 1. ENSURE ENUMS EXIST (Safe Check)
    # ---------------------------------------------------------
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'program_type') THEN
            CREATE TYPE program_type AS ENUM ('REGULAR', 'EVENT');
        END IF;
        
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'student_category') THEN
            CREATE TYPE student_category AS ENUM ('CHILDREN', 'ADOLESCENT', 'YOUTH', 'ADULT');
        END IF;

        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'attendance_status') THEN
            CREATE TYPE attendance_status AS ENUM ('PRESENT', 'ABSENT', 'EXCUSED');
        END IF;
    END$$;
    """)

    # ---------------------------------------------------------
    # 2. CREATE TABLES (Using Raw SQL to avoid Type Conflicts)
    # ---------------------------------------------------------
    
    # Create 'programs'
    op.execute("""
    CREATE TABLE IF NOT EXISTS programs (
        id SERIAL PRIMARY KEY,
        name VARCHAR NOT NULL,
        department_id INTEGER NOT NULL REFERENCES departments(id),
        description VARCHAR,
        type program_type NOT NULL,
        created_by_id INTEGER REFERENCES users(id),
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
        updated_at TIMESTAMP WITHOUT TIME ZONE
    );
    """)

    # Create 'attendance_sessions'
    op.execute("""
    CREATE TABLE IF NOT EXISTS attendance_sessions (
        id SERIAL PRIMARY KEY,
        date DATE NOT NULL,
        department_id INTEGER NOT NULL REFERENCES departments(id),
        program_id INTEGER REFERENCES programs(id),
        target_category student_category NOT NULL,
        type program_type,
        created_by_id INTEGER REFERENCES users(id),
        created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
        updated_at TIMESTAMP WITHOUT TIME ZONE
    );
    """)

    # Create 'attendance_records'
    op.execute("""
    CREATE TABLE IF NOT EXISTS attendance_records (
        id SERIAL PRIMARY KEY,
        session_id INTEGER NOT NULL REFERENCES attendance_sessions(id),
        student_id INTEGER NOT NULL REFERENCES students(id),
        remarks VARCHAR,
        status attendance_status NOT NULL DEFAULT 'PRESENT'
    );
    """)


def downgrade() -> None:
    # Drop tables
    op.execute("DROP TABLE IF EXISTS attendance_records CASCADE")
    op.execute("DROP TABLE IF EXISTS attendance_sessions CASCADE")
    op.execute("DROP TABLE IF EXISTS programs CASCADE")
    
    # We do NOT drop Enums here to avoid breaking other tables