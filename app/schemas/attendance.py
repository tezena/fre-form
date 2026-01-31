from pydantic import BaseModel
from typing import Optional, List
from datetime import date
from app.models.attendance import ProgramType, AttendanceStatus
from app.models.student import StudentCategory

# ProgramType is the canonical enum; alias it for use as AttendanceType in API schemas
AttendanceType = ProgramType


class AttendanceRecordCreate(BaseModel):
    student_id: int
    present: Optional[bool] = True
    notes: Optional[str] = None


class AttendanceSessionCreate(BaseModel):
    date: date
    department_id: int
    category: str
    type: AttendanceType
    records: Optional[List[AttendanceRecordCreate]] = None


# New batch input models
class AttendanceRecordInput(BaseModel):
    student_id: int
    present: bool = False
    notes: Optional[str] = None


class AttendanceBatchCreate(BaseModel):
    date: date
    department_id: int
    category: StudentCategory
    type: ProgramType = ProgramType.REGULAR
    records: List[AttendanceRecordInput]



class AttendanceRecordResponse(BaseModel):
    id: int
    student_id: int
    status: AttendanceStatus
    remarks: Optional[str] = None


class AttendanceSessionResponse(BaseModel):
    id: int
    date: date
    department_id: int
    category: str
    type: AttendanceType
    records: List[AttendanceRecordResponse] = []

    class Config:
        from_attributes = True


class AttendanceRecordCreate(BaseModel):
    student_id: int
    present: Optional[bool] = True
    notes: Optional[str] = None


class AttendanceSessionCreate(BaseModel):
    date: date
    department_id: int
    category: str
    type: AttendanceType
    records: Optional[List[AttendanceRecordCreate]] = None


# New batch input models
class AttendanceRecordInput(BaseModel):
    student_id: int
    present: bool = False
    notes: Optional[str] = None


class AttendanceBatchCreate(BaseModel):
    date: date
    department_id: int
    category: StudentCategory
    type: ProgramType = ProgramType.REGULAR
    records: List[AttendanceRecordInput]



class AttendanceRecordResponse(BaseModel):
    id: int
    student_id: int
    present: bool
    notes: Optional[str] = None


class AttendanceSessionResponse(BaseModel):
    id: int
    date: date
    department_id: int
    category: str
    type: AttendanceType
    records: List[AttendanceRecordResponse] = []

    class Config:
        from_attributes = True
