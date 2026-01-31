from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Annotated, Union, Literal
from datetime import datetime

# Reuse enum from model to avoid divergence
from app.models.student import StudentCategory


class StudentBase(BaseModel):
    name: str
    age: int
    sex: str
    church: Optional[str] = None
    department_id: int


class ChildProfile(BaseModel):
    parentName: str
    parentPhone: str
    schoolName: Optional[str] = None
    grade: Optional[str] = None


from pydantic import model_validator


class ChildFull(BaseModel):
    # Category-specific fields only; common fields are top-level
    photo_url: Optional[str] = None
    category: Literal["CHILDREN"] = StudentCategory.CHILDREN

    parentName: str
    parentPhone: str
    grade: Optional[str] = None
    schoolName: Optional[str] = None


class AdultFull(BaseModel):
    # Category-specific fields only; common fields are top-level
    photo_url: Optional[str] = None
    category: Literal["ADULT"] = StudentCategory.ADULT

    phone: Optional[str] = None
    email: Optional[str] = None
    maritalStatus: Optional[str] = None
    occupation: Optional[str] = None
    education: Optional[str] = None


class YouthFull(BaseModel):
    # Category-specific fields only; common fields are top-level
    photo_url: Optional[str] = None
    category: Literal["YOUTH"] = StudentCategory.YOUTH

    phone: Optional[str] = None
    email: Optional[str] = None
    education: Optional[str] = None
    occupation: Optional[str] = None


class AdolescentFull(BaseModel):
    # Category-specific fields only; common fields are top-level
    photo_url: Optional[str] = None
    category: Literal["ADOLESCENT"] = StudentCategory.ADOLESCENT

    parentName: str
    parentPhone: str
    grade: Optional[str] = None
    schoolName: Optional[str] = None
    phone: Optional[str] = None


class CategoryDetails(BaseModel):
    child: Optional[ChildFull] = None
    Adult: Optional[AdultFull] = None
    youth: Optional[YouthFull] = None
    Adolescent: Optional[AdolescentFull] = None


class StudentCreate(StudentBase):
    category: StudentCategory
    category_details: CategoryDetails

    @model_validator(mode="after")
    def ensure_matching_detail(cls, model):
        cat = model.category
        details = model.category_details
        mapping = {
            StudentCategory.CHILDREN: details.child,
            StudentCategory.ADOLESCENT: details.Adolescent,
            StudentCategory.YOUTH: details.youth,
            StudentCategory.ADULT: details.Adult,
        }
        if mapping.get(cat) is None:
            raise ValueError(f"category_details must include the nested data for {cat}")
        nested = mapping.get(cat)
        if getattr(nested, "category", None) != cat:
            raise ValueError("nested category value must match top-level category")
        return model


class StudentUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    sex: Optional[str] = None
    church: Optional[str] = None
    department_id: Optional[int] = None
    category: Optional[StudentCategory] = None

    # Nested category_details update (partial allowed)
    category_details: Optional[Dict[str, Any]] = None


class StudentResponse(StudentBase):
    id: int
    category: StudentCategory

    category_details: Optional[CategoryDetails] = None

    created_by_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
