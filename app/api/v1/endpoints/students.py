from typing import List, Any, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import get_session
from app.models.student import (
    Student, StudentAddress, StudentFamily, 
    StudentEducation, StudentHealth, StudentSpirituality, 
    StudentCategory
)
from app.models.department import Department
from app.models.user import User, UserRole
from app.schemas.student import StudentCreate, StudentUpdate
from app.core.dependencies import (
    get_current_active_user,
    require_profile_builder_access, # <-- IMPORTED NEW SECURITY GUARD
)
from app.core.utils import mask_student_data

router = APIRouter()

# --- HELPER: Verify User Department Access ---
async def _verify_user_in_department(user: User, department_id: int, session: AsyncSession):
    """Ensures a user is actually assigned to the department they are querying for."""
    if user.role == UserRole.SUPER_ADMIN:
        return True
    
    # Explicitly load the user's departments from the database
    query = select(User).where(User.id == user.id).options(selectinload(User.departments))
    result = await session.execute(query)
    user_with_depts = result.scalar_one()
    
    # Safely check the loaded departments
    user_dept_ids = [d.id for d in user_with_depts.departments]
    if department_id not in user_dept_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to act on behalf of this department."
        )

# --- HELPER: Fetch Full Student ---
async def _fetch_full_student(session: AsyncSession, student_id: int) -> Optional[Student]:
    """Helper to fetch student with all relationships eagerly loaded"""
    query = select(Student).where(Student.id == student_id).options(
        selectinload(Student.address),
        selectinload(Student.family),
        selectinload(Student.education),
        selectinload(Student.health),
        selectinload(Student.spirituality),
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()


# =============================================================================
# 1. WRITE OPERATIONS (Locked to Profile-Builder Only)
# =============================================================================

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_student(
    student_in: StudentCreate,
    # 👇 PLUGGED IN: Only profile-builder or Super Admin can pass this gate
    current_user: User = Depends(require_profile_builder_access),
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Create a new student with a full modular profile. Restricted to Profile Builders."""
    
    # 1. Check if Target Department exists
    dept = await session.get(Department, student_in.department_id)
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")

    # 2. Create Core Student Record
    db_student = Student(
        full_name=student_in.full_name,
        gender=student_in.gender,
        dob=student_in.dob,
        photo_url=student_in.photo_url,
        department_id=student_in.department_id,
        category=student_in.category, 
        created_by_id=current_user.id
    )
    session.add(db_student)
    await session.flush() 

    # 3. Create Address (Required)
    db_address = StudentAddress(student_id=db_student.id, **student_in.address.model_dump())
    session.add(db_address)

    # 4. Extract Category Specific Details
    details = None
    if student_in.category == StudentCategory.CHILDREN:
        details = student_in.category_details.child
    elif student_in.category == StudentCategory.ADULT:
        details = student_in.category_details.adult
    elif student_in.category == StudentCategory.YOUTH:
        details = student_in.category_details.youth
    elif student_in.category == StudentCategory.ADOLESCENT:
        details = student_in.category_details.adolescent

    # 5. Save Modular Sections
    if details:
        if getattr(details, "family", None):
            session.add(StudentFamily(student_id=db_student.id, **details.family.model_dump()))
        if getattr(details, "education", None):
            session.add(StudentEducation(student_id=db_student.id, **details.education.model_dump()))
        if getattr(details, "spirituality", None):
            session.add(StudentSpirituality(student_id=db_student.id, **details.spirituality.model_dump()))
        if getattr(details, "health", None):
            session.add(StudentHealth(student_id=db_student.id, **details.health.model_dump()))
    
    await session.commit()
    
    # Return the unmasked DB object (Since they are the builder, they see everything)
    return await _fetch_full_student(session, db_student.id)


@router.patch("/{student_id}")
async def update_student(
    student_id: int,
    student_in: StudentUpdate,
    # 👇 PLUGGED IN
    current_user: User = Depends(require_profile_builder_access),
    session: AsyncSession = Depends(get_session),
) -> Any:
    """Update a student profile. Restricted to Profile Builders."""
    db_student = await _fetch_full_student(session, student_id)
    if not db_student:
        raise HTTPException(status_code=404, detail="Student not found")

    update_data = student_in.model_dump(exclude_unset=True)
    
    core_fields = {"full_name", "phone", "photo_url", "dob", "department_id"}
    for field in core_fields:
        if field in update_data and update_data[field] is not None:
            setattr(db_student, field, update_data[field])

    async def update_section(model_class, current_instance, new_data_model):
        if not new_data_model:
            return
        data_dict = new_data_model.model_dump(exclude_unset=True)
        if not data_dict:
            return

        if current_instance:
            for key, value in data_dict.items():
                setattr(current_instance, key, value)
            session.add(current_instance)
        else:
            new_instance = model_class(student_id=db_student.id, **data_dict)
            session.add(new_instance)

    await update_section(StudentAddress, db_student.address, student_in.address)
    await update_section(StudentFamily, db_student.family, student_in.family)
    await update_section(StudentEducation, db_student.education, student_in.education)
    await update_section(StudentHealth, db_student.health, student_in.health)
    await update_section(StudentSpirituality, db_student.spirituality, student_in.spirituality)

    await session.commit()
    return await _fetch_full_student(session, student_id)


@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_student(
    student_id: int,
    # 👇 PLUGGED IN
    current_user: User = Depends(require_profile_builder_access),
    session: AsyncSession = Depends(get_session),
):
    """Delete a student. Restricted to Profile Builders."""
    result = await session.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    student.is_active = False # Soft delete
    await session.commit()
    return None


# =============================================================================
# 2. READ OPERATIONS (Dynamic Data Masking for all Departments)
# =============================================================================

@router.get("/", response_model=List[Dict[str, Any]]) 
async def list_students(
    department_id: int = Query(..., description="The ID of the department requesting the data"),
    skip: int = 0,
    limit: int = 100,
    category: Optional[StudentCategory] = None,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
) -> Any:
    """
    List all active students.
    Applies Field-Level Security: Returns only the fields this department is allowed to see.
    """
    await _verify_user_in_department(current_user, department_id, session)
    
    dept = await session.get(Department, department_id)
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")

    query = select(Student).where(Student.is_active == True).offset(skip).limit(limit)
    
    if category:
        query = query.where(Student.category == category)
        
    # Eager load relationships so the masking function can access them if allowed
    query = query.options(
        selectinload(Student.address),
        selectinload(Student.family),
        selectinload(Student.education),
        selectinload(Student.health),
        selectinload(Student.spirituality),
    )

    result = await session.execute(query)
    students = result.scalars().all()

    # Super Admins and the Profile Builder bypass the mask
    if current_user.role == UserRole.SUPER_ADMIN or dept.is_profile_builder:
        # We use a masking function with "None" to denote "give me everything" 
        # (Assuming your mask_student_data handles this, otherwise return raw dicts)
        return [mask_student_data(s, None) for s in students]

    # Mask the data for normal departments
    return [mask_student_data(s, dept.allowed_student_fields) for s in students]


@router.get("/{student_id}", response_model=Dict[str, Any])
async def get_student_detail(
    student_id: int,
    department_id: int = Query(..., description="The ID of the department requesting the data"),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
) -> Any:
    """
    Get a single student.
    Applies Field-Level Security: Returns only the fields this department is allowed to see.
    """
    await _verify_user_in_department(current_user, department_id, session)

    dept = await session.get(Department, department_id)
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")

    student = await _fetch_full_student(session, student_id)
    if not student or not student.is_active:
        raise HTTPException(status_code=404, detail="Student not found")

    if current_user.role == UserRole.SUPER_ADMIN or dept.is_profile_builder:
        return mask_student_data(student, None)

    return mask_student_data(student, dept.allowed_student_fields)