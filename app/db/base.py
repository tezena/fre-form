# app/db/base.py

from app.models.user import User, UserDepartment
from app.models.department import Department
from app.models.student import Student
# Import the actual classes, not the filename
from app.models.attendance import Program, AttendanceSession, AttendanceRecord

# This list tells Alembic what to look for
__all__ = [
    "User", 
    "UserDepartment", 
    "Department", 
    "Student", 
    "Program", 
    "AttendanceSession", 
    "AttendanceRecord"
]