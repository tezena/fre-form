from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, Dict, Any, TYPE_CHECKING
from datetime import datetime
from sqlalchemy import Column, Enum as SQLAEnum, JSON
from enum import Enum as PyEnum

# Prevent circular imports: These run only during type checking, not runtime
if TYPE_CHECKING:
    from app.models.department import Department
    from app.models.user import User


class StudentCategory(str, PyEnum):
    CHILDREN = "CHILDREN"
    ADOLESCENT = "ADOLESCENT"
    YOUTH = "YOUTH"
    ADULT = "ADULT"


class Student(SQLModel, table=True):
    """Student model with explicit flat profile columns to match API shape."""
    __tablename__ = "students"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    age: int
    sex: str
    church: Optional[str] = None

    # Category discriminator stored as SQL Enum
    category: StudentCategory = Field(
        sa_column=Column(SQLAEnum(StudentCategory, name="student_category")),
        default=StudentCategory.CHILDREN,
    )

    # Flexible JSON column to hold nested profile object per category
    profile_data: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

    # Convenience property named `profile` to map to `profile_data` for Pydantic responses
    @property
    def profile(self) -> Optional[Dict[str, Any]]:
        return self.profile_data

    @profile.setter
    def profile(self, value: Optional[Dict[str, Any]]):
        self.profile_data = value

    # Provide `category_details` property that returns an object with keys
    # for each category; only the active category will be populated
    @property
    def category_details(self) -> Dict[str, Any]:
        details = {
            "child": None,
            "Adult": None,
            "youth": None,
            "Adolescent": None,
        }
        if self.profile_data:
            if self.category == StudentCategory.CHILDREN:
                details["child"] = self.profile_data
            elif self.category == StudentCategory.ADOLESCENT:
                details["Adolescent"] = self.profile_data
            elif self.category == StudentCategory.YOUTH:
                details["youth"] = self.profile_data
            elif self.category == StudentCategory.ADULT:
                details["Adult"] = self.profile_data
        return details

    @category_details.setter
    def category_details(self, value: Dict[str, Any]):
        # Accept either full category_details object or a single nested dict
        if not value:
            self.profile_data = None
            return
        # priority: use the nested object that matches current category if present
        if self.category == StudentCategory.CHILDREN and value.get("child") is not None:
            self.profile_data = value.get("child")
        elif self.category == StudentCategory.ADOLESCENT and value.get("Adolescent") is not None:
            self.profile_data = value.get("Adolescent")
        elif self.category == StudentCategory.YOUTH and value.get("youth") is not None:
            self.profile_data = value.get("youth")
        elif self.category == StudentCategory.ADULT and value.get("Adult") is not None:
            self.profile_data = value.get("Adult")
        else:
            # fallback: if a single nested value is provided (no wrapper), accept it
            # value might be the nested dict itself
            if any(k in value for k in ["parentName", "parentPhone", "phone", "education"]):
                self.profile_data = value
            else:
                self.profile_data = None

    # Foreign Keys
    department_id: int = Field(foreign_key="departments.id")
    created_by_id: Optional[int] = Field(default=None, foreign_key="users.id")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    # Relationships
    department: "Department" = Relationship(back_populates="students")
    created_by_user: Optional["User"] = Relationship(back_populates="students")