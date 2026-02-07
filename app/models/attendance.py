from typing import Optional, List, TYPE_CHECKING
from datetime import date, datetime
from enum import Enum as PyEnum

from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, Enum as SQLAEnum

# Import StudentCategory from your existing student model
from app.models.student import StudentCategory

if TYPE_CHECKING:
    # Avoid circular imports for type checking
    from app.models.student import Student
    from app.models.user import User

# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------
class ProgramType(str, PyEnum):
    REGULAR = "REGULAR"
    EVENT = "EVENT"

class AttendanceStatus(str, PyEnum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    EXCUSED = "EXCUSED"

# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------

class Program(SQLModel, table=True):
    __tablename__ = "programs"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    department_id: int = Field(foreign_key="departments.id")
    description: Optional[str] = None
    
    # Use 'program_type' as the Postgres Enum name
    type: ProgramType = Field(
        sa_column=Column(SQLAEnum(ProgramType, name="program_type"), nullable=False)
    )

    created_by_id: Optional[int] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    # Relationships
    sessions: List["AttendanceSession"] = Relationship(back_populates="program")


class AttendanceSession(SQLModel, table=True):
    __tablename__ = "attendance_sessions"

    id: Optional[int] = Field(default=None, primary_key=True)
    date: date
    department_id: int = Field(foreign_key="departments.id")
    program_id: Optional[int] = Field(default=None, foreign_key="programs.id")
    
    # Target Category (Reusing the existing 'student_category' Postgres Enum)
    target_category: StudentCategory = Field(
        sa_column=Column(SQLAEnum(StudentCategory, name="student_category"), nullable=False)
    )

    # Legacy Type Field (Optional) 
    # NOTE: mapped to the SAME 'program_type' enum to avoid creating duplicates in DB
    type: Optional[ProgramType] = Field(
        default=None, 
        sa_column=Column(SQLAEnum(ProgramType, name="program_type"), nullable=True)
    )

    created_by_id: Optional[int] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    # Relationships
    records: List["AttendanceRecord"] = Relationship(back_populates="session")
    program: Optional["Program"] = Relationship(back_populates="sessions")


class AttendanceRecord(SQLModel, table=True):
    __tablename__ = "attendance_records"

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="attendance_sessions.id")
    student_id: int = Field(foreign_key="students.id")
    remarks: Optional[str] = None

    # Status Enum
    status: AttendanceStatus = Field(
        sa_column=Column(SQLAEnum(AttendanceStatus, name="attendance_status"), nullable=False, default=AttendanceStatus.PRESENT),
        default=AttendanceStatus.PRESENT
    )

    # Relationships
    session: "AttendanceSession" = Relationship(back_populates="records")