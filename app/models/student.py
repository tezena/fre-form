from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, Dict, Any, TYPE_CHECKING
from datetime import datetime
from sqlalchemy import JSON  # <--- Essential import for Postgres JSONB

# Prevent circular imports: These run only during type checking, not runtime
if TYPE_CHECKING:
    from app.models.department import Department
    from app.models.user import User

class Student(SQLModel, table=True):
    """Student model."""
    __tablename__ = "students"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    age: int
    sex: str
    education_level: str
    photo_url: Optional[str] = None
    
    # FIX: Correct way to define JSON field for Postgres
    family_profile: Optional[Dict[str, Any]] = Field(default=None, sa_type=JSON)
    
    phone: Optional[str] = None
    
    # Foreign Keys
    department_id: int = Field(foreign_key="departments.id")
    created_by_id: Optional[int] = Field(default=None, foreign_key="users.id")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    # Relationships
    # using string forward references "Department" and "User" is perfect here
    department: "Department" = Relationship(back_populates="students")
    created_by_user: Optional["User"] = Relationship(back_populates="students")