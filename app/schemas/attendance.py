from pydantic import BaseModel
from typing import Optional, List
from datetime import date
from app.models.attendance import ProgramType, AttendanceStatus
from app.models.student import StudentCategory

# --- SHARED / BASE MODELS ---

class AttendanceRecordInput(BaseModel):
    """Used for inputting data (creating/updating)"""
    student_id: int
    present: bool = False
    notes: Optional[str] = None

# --- CREATION MODELS ---

class AttendanceBatchCreate(BaseModel):
    """
    Used for the /batch endpoint.
    Strictly validates category against the Enum.
    """
    date: date
    department_id: int
    category: StudentCategory  # <--- FIX: Enforces "CHILDREN", "YOUTH", etc.
    type: ProgramType = ProgramType.REGULAR
    records: List[AttendanceRecordInput]


class AttendanceSessionCreate(BaseModel):
    """
    Used for the /sessions/ (manual creation) endpoint.
    """
    date: date
    department_id: int
    category: StudentCategory # <--- FIX: Changed from str to StudentCategory
    type: ProgramType
    records: Optional[List[AttendanceRecordInput]] = None


class AttendanceRecordCreate(BaseModel):
    """Used for adding a single record to an existing session"""
    student_id: int
    present: bool = True
    notes: Optional[str] = None


# --- RESPONSE MODELS ---

class AttendanceRecordResponse(BaseModel):
    """
    Returns data to the frontend.
    Matches the 'attendance_records' table structure.
    """
    id: int
    student_id: int
    status: AttendanceStatus # Returns "PRESENT", "ABSENT", etc.
    remarks: Optional[str] = None

    class Config:
        from_attributes = True


class AttendanceSessionResponse(BaseModel):
    """
    Returns session details + list of records.
    """
    id: int
    date: date
    department_id: int
    category: StudentCategory # Returns the Enum value
    type: ProgramType
    records: List[AttendanceRecordResponse] = []

    class Config:
        from_attributes = True