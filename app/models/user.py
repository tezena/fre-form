from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from enum import Enum
from datetime import datetime

# We use TYPE_CHECKING to avoid circular imports at runtime
if TYPE_CHECKING:
    from app.models.department import Department
    from app.models.student import Student

class UserRole(str, Enum):
    """User role enumeration."""
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    MANAGER = "manager"

# --- FIX 1: Define the Link Model FIRST ---
class UserDepartment(SQLModel, table=True):
    """Many-to-many relationship between Users and Departments."""
    __tablename__ = "user_departments"

    user_id: int = Field(foreign_key="users.id", primary_key=True)
    department_id: int = Field(foreign_key="departments.id", primary_key=True)

# --- FIX 2: Define the User Model SECOND ---
class User(SQLModel, table=True):
    """User model with role-based access control."""
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    password_hash: str
    full_name: str
    role: UserRole
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    # Relationships
    # FIX 3: pass the CLASS UserDepartment, not the string "UserDepartment"
    departments: List["Department"] = Relationship(
        back_populates="users", 
        link_model=UserDepartment 
    )
    
    students: List["Student"] = Relationship(back_populates="created_by_user")

    class Config:
        populate_by_name = True