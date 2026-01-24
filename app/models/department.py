from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime

# 1. Import the Link Model Class directly (Essential for the Relationship to work)
# Assuming you kept UserDepartment in app/models/user.py
from app.models.user import UserDepartment

# 2. Avoid Circular Imports for the related models
if TYPE_CHECKING:
    from app.models.user import User
    from app.models.student import Student

class Department(SQLModel, table=True):
    """Department model."""
    __tablename__ = "departments"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    # Relationships
    
    # FIX: Use the imported class UserDepartment, NOT a string
    users: List["User"] = Relationship(
        back_populates="departments", 
        link_model=UserDepartment 
    )
    
    students: List["Student"] = Relationship(back_populates="department")