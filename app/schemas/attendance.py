from pydantic import BaseModel
from typing import Optional, List
from datetime import date , timezone
from app.models.attendance import ProgramType, AttendanceStatus , Program
from app.models.student import StudentCategory
from app.models.enums import Gender, StudentCategory


# --- 2. ATTENDANCE RECORD SCHEMAS ---
class AttendanceRecordCreate(BaseModel):
    student_id: int
    status: AttendanceStatus 
    notes: Optional[str] = None


# --- 3. ATTENDANCE BATCH SCHEMA (UPDATED) ---
class AttendanceBatchCreate(BaseModel):
    date: date
    program_id: int           # <--- We now require exactly which program this is for
    category: StudentCategory # Which group of students are we tracking today?
    records: List[AttendanceRecordCreate]



class AttendanceSessionCreate(BaseModel):
    """
    Used for the /sessions/ (manual creation) endpoint.
    """
    date: date
    program_id: int 
    category: StudentCategory # <--- FIX: Changed from str to StudentCategory
    records: Optional[List[AttendanceRecordCreate]] = None

class AttendanceSessionUpdate(BaseModel):
    date: date

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
    program_id: int 
    category: StudentCategory # Returns the Enum value
    type: ProgramType
    records: List[AttendanceRecordResponse] = []
    is_active: bool

    class Config:
        from_attributes = True



class StudentAttendanceList(BaseModel):
    """Extremely lightweight schema for the attendance checklist UI"""
    id: int
    full_name: str
    photo_url: Optional[str] = None
    gender: Gender
    dob: date
    category: StudentCategory

    class Config:
        from_attributes = True