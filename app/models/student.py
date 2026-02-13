from typing import Optional, List, Dict, Any
from datetime import date, datetime
from sqlmodel import SQLModel, Field, Relationship, JSON
from sqlalchemy import Column, JSON, Enum as SQLAEnum
from app.models.user import User
from app.models.enums import (
    Gender, MaritalStatus, EducationLevel, 
    OccupationStatus, ChurchAttendance, StudentCategory
)

# --- 1. CORE TABLE ---
class Student(SQLModel, table=True):
    __tablename__ = "students"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    full_name: str = Field(index=True)
    photo_url: Optional[str] = None
    gender: Gender
    dob: date
    
    # Category Management
    category: StudentCategory = Field(
        sa_column=Column(SQLAEnum(StudentCategory, name="student_category")),
        default=StudentCategory.CHILDREN,
    )
    department_id: int = Field(foreign_key="departments.id")
    department: "Department" = Relationship()

    created_by_user: Optional["User"] = Relationship(
        sa_relationship_kwargs={
            "primaryjoin": "Student.created_by_id==User.id",
            "lazy": "selectin"
        }
    )
    
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by_id: Optional[int] = Field(default=None, foreign_key="users.id")
    
    # Relationships (One-to-One)
    address: Optional["StudentAddress"] = Relationship(back_populates="student", sa_relationship_kwargs={"uselist": False})
    education: Optional["StudentEducation"] = Relationship(back_populates="student", sa_relationship_kwargs={"uselist": False})
    health: Optional["StudentHealth"] = Relationship(back_populates="student", sa_relationship_kwargs={"uselist": False})
    family: Optional["StudentFamily"] = Relationship(back_populates="student", sa_relationship_kwargs={"uselist": False})
    spirituality: Optional["StudentSpirituality"] = Relationship(back_populates="student", sa_relationship_kwargs={"uselist": False})


# --- 2. ADDRESS & DEMOGRAPHICS ---
class StudentAddress(SQLModel, table=True):
    __tablename__ = "student_addresses"
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="students.id", unique=True)
    
    nationality: str = Field(default="Ethiopian")
    marital_status: Optional[MaritalStatus] = None
    
    # Birth Place
    birth_region: Optional[str] = None
    birth_zone: Optional[str] = None
    birth_city: Optional[str] = None
    birth_woreda: Optional[str] = None
    birth_kebele: Optional[str] = None
    
    # Current Location
    current_region: Optional[str] = None
    current_zone: Optional[str] = None
    current_city: Optional[str] = None
    current_woreda: Optional[str] = None
    current_kebele: Optional[str] = None
    
    student: Student = Relationship(back_populates="address")


# --- 3. EDUCATION & WORK ---
class StudentEducation(SQLModel, table=True):
    __tablename__ = "student_education"
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="students.id", unique=True)
    
    level: Optional[EducationLevel] = None
    occupation: Optional[OccupationStatus] = None
    
    # Higher Ed Details
    college_name: Optional[str] = None
    department_name: Optional[str] = None
    entry_year: Optional[str] = None 
    certificate_type: Optional[str] = None
    
    # Languages (Stored as JSON)
    languages:  List[Dict[str, Any]] = Field(default=[], sa_column=Column(JSON))
    
    student: Student = Relationship(back_populates="education")


# --- 4. HEALTH & EMERGENCY ---
class StudentHealth(SQLModel, table=True):
    __tablename__ = "student_health"
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="students.id", unique=True)
    
    has_disability: bool = False
    disability_details: Optional[str] = None
    
    has_trauma: bool = False
    trauma_details: Optional[str] = None
    
    health_issues: Optional[str] = None
    mental_status: Optional[str] = None
    
    # Emergency Contact
    emergency_name: Optional[str] = None
    emergency_phone: Optional[str] = None
    emergency_relation: Optional[str] = None
    
    student: Student = Relationship(back_populates="health")


# --- 5. SPIRITUALITY & HISTORY ---
class StudentSpirituality(SQLModel, table=True):
    __tablename__ = "student_spirituality"
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="students.id", unique=True)
    
    baptism_name: Optional[str] = None
    baptism_place: Optional[str] = None
    
    has_spiritual_father: bool = False
    spiritual_father_name: Optional[str] = None
    spiritual_father_phone: Optional[str] = None
    
    has_holy_orders: bool = False 
    
    # Sunday School History
    joined_sunday_school_date: Optional[date] = None
    reason_for_joining: Optional[str] = None
    short_bio: Optional[str] = None
    
    student: Student = Relationship(back_populates="spirituality")


# --- 6. FAMILY INFO ---
class StudentFamily(SQLModel, table=True):
    __tablename__ = "student_family"
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="students.id", unique=True)
    
    # Father
    father_alive: bool = True
    father_name: Optional[str] = None
    father_phone: Optional[str] = None
    father_occupation: Optional[str] = None
    father_dob: Optional[date] = None            
    father_pob: Optional[str] = None             
    father_education_level: Optional[EducationLevel] = None 
    father_disability: Optional[str] = None      
    
    # Mother
    mother_alive: bool = True
    mother_name: Optional[str] = None
    mother_phone: Optional[str] = None
    mother_occupation: Optional[str] = None
    mother_dob: Optional[date] = None            
    mother_pob: Optional[str] = None             
    mother_education_level: Optional[EducationLevel] = None 
    mother_disability: Optional[str] = None      
    
    # Guardian
    guardian_name: Optional[str] = None
    guardian_phone: Optional[str] = None
    guardian_relation: Optional[str] = None
    
    # Family Context
    parents_have_spiritual_father: bool = False
    parents_spiritual_visit_freq: Optional[str] = None
    parents_church_freq: Optional[ChurchAttendance] = None
    orthodox_awareness_level: Optional[str] = None
    family_members_living_together: Optional[str] = None
    
    student: Student = Relationship(back_populates="family")