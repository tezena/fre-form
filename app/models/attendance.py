from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import date, datetime
from sqlalchemy import Column, Enum as SQLAEnum
from enum import Enum as PyEnum
from typing import TYPE_CHECKING

# Reuse StudentCategory enum to keep values consistent
from app.models.student import StudentCategory

if TYPE_CHECKING:
    from app.models.student import Student


class ProgramType(str, PyEnum):
    REGULAR = "REGULAR"
    EVENT = "EVENT"


class AttendanceStatus(str, PyEnum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    EXCUSED = "EXCUSED"


class Program(SQLModel, table=True):
    __tablename__ = "programs"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    department_id: int = Field(foreign_key="departments.id")
    type: ProgramType = Field(sa_column=Column(SQLAEnum(ProgramType, name="program_type")))
    description: Optional[str] = None

    created_by_id: Optional[int] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    sessions: List["AttendanceSession"] = Relationship(back_populates="program")


class AttendanceSession(SQLModel, table=True):
    __tablename__ = "attendance_sessions"

    id: Optional[int] = Field(default=None, primary_key=True)
    date: date
    department_id: int = Field(foreign_key="departments.id")
    # legacy: keep 'type' available but the canonical relationship is via Program
    type: Optional[ProgramType] = Field(default=None, sa_column=Column(SQLAEnum(ProgramType, name="attendance_type")))
    # target_category is the student category this session applies to
    target_category: StudentCategory = Field(sa_column=Column(SQLAEnum(StudentCategory, name="student_category")))

    program_id: Optional[int] = Field(default=None, foreign_key="programs.id")

    created_by_id: Optional[int] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    records: List["AttendanceRecord"] = Relationship(back_populates="session")
    program: Optional["Program"] = Relationship(back_populates="sessions")


class AttendanceRecord(SQLModel, table=True):
    __tablename__ = "attendance_records"

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="attendance_sessions.id")
    student_id: int = Field(foreign_key="students.id")
    status: AttendanceStatus = Field(sa_column=Column(SQLAEnum(AttendanceStatus, name="attendance_status")), default=AttendanceStatus.PRESENT)
    remarks: Optional[str] = None

    session: "AttendanceSession" = Relationship(back_populates="records")
