from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class StudentBase(BaseModel):
    name: str
    age: int
    sex: str
    education_level: str
    photo_url: Optional[str] = None
    family_profile: Optional[Dict[str, Any]] = None
    phone: Optional[str] = None
    department_id: int


class StudentCreate(StudentBase):
    pass


class StudentUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    sex: Optional[str] = None
    education_level: Optional[str] = None
    photo_url: Optional[str] = None
    family_profile: Optional[Dict[str, Any]] = None
    phone: Optional[str] = None
    department_id: Optional[int] = None


class StudentResponse(StudentBase):
    id: int
    created_by_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

