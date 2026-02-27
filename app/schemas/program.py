from pydantic import BaseModel
from typing import Optional, List
from datetime import date
from app.models.attendance import ProgramType, AttendanceStatus , Program
from app.models.student import StudentCategory
from app.models.enums import Gender, StudentCategory


# --- 1. PROGRAM SCHEMAS ---
class ProgramCreate(BaseModel):
    name: str
    department_id: int
    type: ProgramType
    description: Optional[str] = None

class ProgramUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[ProgramType] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None  # Allow admins to reactivate an archived program

class ProgramResponse(ProgramCreate):
    id: int
    is_active: bool  # Make sure the frontend knows if it's active

    class Config:
        from_attributes = True