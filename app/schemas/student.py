from pydantic import BaseModel, Field, model_validator
from typing import Optional, List, Dict, Any, Literal
from datetime import date , datetime
from app.models.enums import (
    Gender, MaritalStatus, EducationLevel, 
    OccupationStatus, ChurchAttendance, StudentCategory
)
from app.models.student import StudentCategory # Ensure this is your Enum

# --- 1. SHARED COMPONENTS (Used in all forms) ---

class AddressCreate(BaseModel):
    # Birth Place
    birth_region: Optional[str] = None
    birth_zone: Optional[str] = None
    birth_city: Optional[str] = None
    birth_woreda: Optional[str] = None
    birth_kebele: Optional[str] = None
    
    # Current Location
    current_region: str
    current_zone: str
    current_city: str
    current_woreda: Optional[str] = None
    current_kebele: Optional[str] = None
    
    nationality: str = "Ethiopian"

class EducationCreate(BaseModel):
    level: EducationLevel
    occupation: OccupationStatus
    
    # Optional High Ed info
    college_name: Optional[str] = None
    department_name: Optional[str] = None
    entry_year: Optional[str] = None
    certificate_type: Optional[str] = None
    
    # Languages [{"lang": "Amharic", "rate": 5}]
    languages: List[Dict[str, Any]] = []

class HealthCreate(BaseModel):
    has_disability: bool = False
    disability_details: Optional[str] = None
    has_trauma: bool = False
    trauma_details: Optional[str] = None
    health_issues: Optional[str] = None
    mental_status: Optional[str] = None
    
    # Emergency
    emergency_name: str
    emergency_phone: str
    emergency_relation: str

class SpiritualityCreate(BaseModel):
    baptism_name: Optional[str] = None
    baptism_place: Optional[str] = None
    has_spiritual_father: bool = False
    spiritual_father_name: Optional[str] = None
    spiritual_father_phone: Optional[str] = None
    has_holy_orders: bool = False

# --- 2. FAMILY INPUTS (Mainly for Children/Adolescents) ---

class FamilyCreate(BaseModel):
    # --- FATHER INFO ---
    father_alive: bool = True
    father_name: Optional[str] = None
    father_phone: Optional[str] = None
    father_occupation: Optional[str] = None
    father_dob: Optional[date] = None
    father_pob: Optional[str] = None  # Place of Birth
    father_education_level: Optional[EducationLevel] = None
    father_disability: Optional[str] = None  # Text description (e.g., "Blindness") or None

    # --- MOTHER INFO ---
    mother_alive: bool = True
    mother_name: Optional[str] = None
    mother_phone: Optional[str] = None
    mother_occupation: Optional[str] = None
    mother_dob: Optional[date] = None
    mother_pob: Optional[str] = None
    mother_education_level: Optional[EducationLevel] = None
    mother_disability: Optional[str] = None

    # --- GUARDIAN INFO (Optional) ---
    guardian_name: Optional[str] = None
    guardian_relation: Optional[str] = None
    guardian_phone: Optional[str] = None

    # --- FAMILY CONTEXT ---
    parents_church_freq: Optional[ChurchAttendance] = None
    parents_have_spiritual_father: bool = False
    parents_spiritual_visit_freq: Optional[str] = None
    family_members_living_together: Optional[str] = None
    orthodox_awareness_level: Optional[str] = None

# --- 3. CATEGORY SPECIFIC INPUTS ---

class ChildInput(BaseModel):
    """Strict requirements for Children"""
    family: FamilyCreate  # REQUIRED for children
    education: Optional[EducationCreate] = None # Optional (maybe too young)
    spirituality: Optional[SpiritualityCreate] = None
    health: Optional[HealthCreate] = None

class AdultInput(BaseModel):
    """Strict requirements for Adults"""
    marital_status: MaritalStatus # REQUIRED for adults
    phone: str # REQUIRED for adults
    email: Optional[str] = None
    
    education: EducationCreate # REQUIRED for adults (work info)
    spirituality: SpiritualityCreate
    health: Optional[HealthCreate] = None
    # Note: 'family' is usually skipped for adults

class YouthInput(BaseModel):
    """Requirements for Youth"""
    phone: str
    education: EducationCreate 
    family: Optional[FamilyCreate] = None # Optional
    spirituality: SpiritualityCreate
    health: Optional[HealthCreate] = None

# --- 4. THE MASTER REGISTRATION FORM ---

class CategoryDetails(BaseModel):
    child: Optional[ChildInput] = None
    adult: Optional[AdultInput] = None
    youth: Optional[YouthInput] = None
    adolescent: Optional[ChildInput] = None # Re-use ChildInput or make custom

class StudentCreate(BaseModel):
    # Top Level Basic Info
    full_name: str
    gender: Gender
    dob: date
    photo_url: Optional[str] = None
    
    department_id: int
    category: StudentCategory
    
    address: AddressCreate
    
    # The Magic Switch
    category_details: CategoryDetails

    @model_validator(mode="after")
    def validate_category_data(self):
        """
        Ensures that if category='CHILDREN', the 'child' data is present.
        """
        cat = self.category
        details = self.category_details
        
        if cat == StudentCategory.CHILDREN and not details.child:
            raise ValueError("Category is CHILDREN but 'child' details are missing.")
        
        if cat == StudentCategory.ADULT and not details.adult:
            raise ValueError("Category is ADULT but 'adult' details are missing.")
            
        if cat == StudentCategory.YOUTH and not details.youth:
            raise ValueError("Category is YOUTH but 'youth' details are missing.")
            
        return self


# ==========================================
# 3. UPDATE SCHEMAS (For Editing)
# ==========================================

class StudentUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    photo_url: Optional[str] = None
    dob: Optional[date] = None
    category: Optional[StudentCategory] = None
    department_id: Optional[int] = None
    
    # Nested Updates (All fields optional by default in Pydantic v2 if not required)
    address: Optional[AddressCreate] = None
    family: Optional[FamilyCreate] = None
    education: Optional[EducationCreate] = None
    spirituality: Optional[SpiritualityCreate] = None
    health: Optional[HealthCreate] = None


# ==========================================
# 4. RESPONSE SCHEMAS (What the API returns)
# ==========================================

class AddressResponse(AddressCreate):
    id: int
    student_id: int

class EducationResponse(EducationCreate):
    id: int
    student_id: int

class FamilyResponse(FamilyCreate):
    id: int
    student_id: int

class SpiritualityResponse(SpiritualityCreate):
    id: int
    student_id: int

class HealthResponse(HealthCreate):
    id: int
    student_id: int

class StudentResponse(BaseModel):
    id: int
    full_name: str
    gender: Gender
    dob: date
    photo_url: Optional[str] = None
    category: StudentCategory
    department_id: int
    is_active: bool
    created_at: datetime
    
    # Nested Objects
    address: Optional[AddressResponse] = None
    education: Optional[EducationResponse] = None
    family: Optional[FamilyResponse] = None
    spirituality: Optional[SpiritualityResponse] = None
    health: Optional[HealthResponse] = None

    class Config:
        from_attributes = True

class StudentSummary(BaseModel):
    """Lightweight schema for list views"""
    id: int
    full_name: str
    category: StudentCategory
    gender: Gender
    dob: date
    photo_url: Optional[str] = None
    department_id: int
    # We include just enough to show location in a table
    address: Optional[AddressResponse] = None

    class Config:
        from_attributes = True