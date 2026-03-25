from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

class DepartmentBase(BaseModel):
    name: str
    description: Optional[str] = None
    
    # 👇 ADD THESE TWO NEW FIELDS 👇
    is_profile_builder: bool = False
    allowed_student_fields: Optional[List[str]] = None

class DepartmentCreate(DepartmentBase):
    pass

class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    
    # 👇 MAKE THEM OPTIONAL FOR UPDATES 👇
    is_profile_builder: Optional[bool] = None
    allowed_student_fields: Optional[List[str]] = None

class DepartmentResponse(DepartmentBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True