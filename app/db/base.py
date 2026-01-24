"""
Import all models here for Alembic to detect them.
"""
from app.models.user import User, UserDepartment
from app.models.department import Department
from app.models.student import Student

__all__ = ["User", "UserDepartment", "Department", "Student"]

