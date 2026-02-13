from typing import List, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
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
from app.schemas.student import (
    StudentCreate, 
    StudentResponse, 
    StudentUpdate, 
    StudentSummary
)
from app.core.dependencies import (
    get_current_active_user,
    get_current_super_admin,
    check_admin_department_access,
    get_user_departments,
)

router = APIRouter()

# --- 1. CREATE STUDENT ---
@router.post("/", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
async def create_student(
    student_in: StudentCreate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
) -> Any:
    """
    Create a new student with a full modular profile.
    - Validates Department Access.
    - Splits data into Address, Family, Education, etc. tables.
    """
    # 1. Permission Check: Can this user add to this department?
    if current_user.role != UserRole.SUPER_ADMIN:
        has_access = await check_admin_department_access(
            current_user.id, student_in.department_id, session
        )
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You do not have access to department {student_in.department_id}"
            )

    # 2. Check if Department exists (Double check)
    dept = await session.get(Department, student_in.department_id)
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")

    # 3. Create Core Student Record
    # We convert the category Enum to a string for the DB (if your DB uses string) 
    # or keep as Enum if your model uses Enum.
    db_student = Student(
        full_name=student_in.full_name,
        gender=student_in.gender,
        dob=student_in.dob,
        photo_url=student_in.photo_url,
        department_id=student_in.department_id,
        category=student_in.category, # Model handles the Enum
        created_by_id=current_user.id
    )
    session.add(db_student)
    await session.flush() # Flush to get the ID

    # 4. Create Address (Required)
    db_address = StudentAddress(
        student_id=db_student.id,
        **student_in.address.model_dump()
    )
    session.add(db_address)

    # 5. Extract Category Specific Details
    details = None
    if student_in.category == StudentCategory.CHILDREN:
        details = student_in.category_details.child
    elif student_in.category == StudentCategory.ADULT:
        details = student_in.category_details.adult
    elif student_in.category == StudentCategory.YOUTH:
        details = student_in.category_details.youth
    elif student_in.category == StudentCategory.ADOLESCENT:
        details = student_in.category_details.adolescent

    # 6. Save Modular Sections (if provided)
    if details:
        # -- Family --
        if getattr(details, "family", None):
            db_family = StudentFamily(
                student_id=db_student.id,
                **details.family.model_dump()
            )
            session.add(db_family)
            
        # -- Education --
        if getattr(details, "education", None):
            db_edu = StudentEducation(
                student_id=db_student.id,
                **details.education.model_dump()
            )
            session.add(db_edu)

        # -- Spirituality --
        if getattr(details, "spirituality", None):
            db_spirit = StudentSpirituality(
                student_id=db_student.id,
                **details.spirituality.model_dump()
            )
            session.add(db_spirit)

        # -- Health --
        if getattr(details, "health", None):
            db_health = StudentHealth(
                student_id=db_student.id,
                **details.health.model_dump()
            )
            session.add(db_health)
    
    await session.commit()
    
    # 7. Refresh with all relations loaded for the response
    return await _fetch_full_student(session, db_student.id)

@router.get("/detailed/", response_model=List[StudentResponse])
async def list_students_detailed(
    skip: int = 0,
    limit: int = 50,
    department_id: Optional[int] = Query(None),
    category: Optional[StudentCategory] = None,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
) -> Any:
    """
    Get a FULL DETAILED list of students.
    Fetches Family, Education, Health, etc. for everyone.
    """
    query = select(Student).offset(skip).limit(limit)

    # Permission Filter
    query = await _apply_permission_filter(query, current_user, session, department_id)

    # Category Filter
    if category:
        query = query.where(Student.category == category)

    # Eager Load EVERYTHING
    query = query.options(
        selectinload(Student.address),
        selectinload(Student.family),
        selectinload(Student.education),
        selectinload(Student.health),
        selectinload(Student.spirituality),
    )

    result = await session.execute(query)
    return result.scalars().all()
# --- 3. LIST STUDENTS ---
@router.get("/", response_model=List[StudentSummary])
async def list_students(
    skip: int = 0,
    limit: int = 100,
    department_id: Optional[int] = Query(None, description="Filter by department ID"),
    category: Optional[StudentCategory] = None,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
) -> Any:
    """
    List students (Summary View).
    - Admins see only their departments.
    - Super Admins see all (or filtered).
    """
    query = select(Student).offset(skip).limit(limit)

    # 1. Filter by User Access
    if current_user.role != UserRole.SUPER_ADMIN:
        user_dept_ids = await get_user_departments(current_user.id, session)
        if not user_dept_ids:
            return [] # No access to any departments
        
        # If user asks for specific dept, check if they own it
        if department_id:
            if department_id not in user_dept_ids:
                raise HTTPException(status_code=403, detail="Access denied to this department")
            query = query.where(Student.department_id == department_id)
        else:
            # Show all depts they own
            query = query.where(Student.department_id.in_(user_dept_ids))
    else:
        # Super Admin logic
        if department_id:
            query = query.where(Student.department_id == department_id)

    # 2. Filter by Category
    if category:
        query = query.where(Student.category == category)

    # 3. Load basic relations for the summary (e.g. Address for location)
    query = query.options(selectinload(Student.address))

    result = await session.execute(query)
    students = result.scalars().all()
    return students


# --- 2. GET STUDENT (READ) ---
@router.get("/{student_id}", response_model=StudentResponse)
async def get_student(
    student_id: int,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
) -> Any:
    """
    Get full student profile.
    - Checks if user has access to the student's department.
    """
    student = await _fetch_full_student(session, student_id)
    
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Permission Check
    if current_user.role != UserRole.SUPER_ADMIN:
        has_access = await check_admin_department_access(
            current_user.id, student.department_id, session
        )
        if not has_access:
            raise HTTPException(
                status_code=403, 
                detail="You do not have access to this student's department"
            )

    return student








# --- 3. GET SINGLE STUDENT (DETAILED) ---
# Use this when clicking on a specific student.
@router.get("/detail/{student_id}", response_model=StudentResponse)
async def get_student_detail(
    student_id: int,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
) -> Any:
    """
    Get FULL profile of a single student by ID.
    """
    query = select(Student).where(Student.id == student_id).options(
        selectinload(Student.address),
        selectinload(Student.family),
        selectinload(Student.education),
        selectinload(Student.health),
        selectinload(Student.spirituality),
    )
    
    result = await session.execute(query)
    student = result.scalar_one_or_none()
    
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Permission Check
    if current_user.role != UserRole.SUPER_ADMIN:
        has_access = await check_admin_department_access(
            current_user.id, student.department_id, session
        )
        if not has_access:
            raise HTTPException(status_code=403, detail="Access denied")

    return student


# --- HELPER: Permission Logic ---
# Since we use the same permission logic in two places, let's extract it.
async def _apply_permission_filter(query, current_user, session, filter_dept_id):
    if current_user.role != UserRole.SUPER_ADMIN:
        user_dept_ids = await get_user_departments(current_user.id, session)
        if not user_dept_ids:
            # If user has no departments, return a query that finds nothing
            return query.where(Student.id == -1) 
        
        if filter_dept_id:
            if filter_dept_id not in user_dept_ids:
                raise HTTPException(status_code=403, detail="Access denied")
            return query.where(Student.department_id == filter_dept_id)
        else:
            return query.where(Student.department_id.in_(user_dept_ids))
    else:
        # Super Admin
        if filter_dept_id:
            return query.where(Student.department_id == filter_dept_id)
    
    return query

# --- 4. UPDATE STUDENT ---
@router.patch("/{student_id}", response_model=StudentResponse)
async def update_student(
    student_id: int,
    student_in: StudentUpdate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
) -> Any:
    """
    Update a student profile (Core info or Nested tables).
    """
    # 1. Fetch existing
    db_student = await _fetch_full_student(session, student_id)
    if not db_student:
        raise HTTPException(status_code=404, detail="Student not found")

    # 2. Permission Check
    if current_user.role != UserRole.SUPER_ADMIN:
        has_access = await check_admin_department_access(
            current_user.id, db_student.department_id, session
        )
        if not has_access:
            raise HTTPException(status_code=403, detail="Access denied")

    # 3. Update Core Fields
    update_data = student_in.model_dump(exclude_unset=True)
    
    # Handle core fields explicitly to avoid recursion issues with nested models
    core_fields = {"full_name", "phone", "photo_url", "dob", "department_id"}
    for field in core_fields:
        if field in update_data and update_data[field] is not None:
            setattr(db_student, field, update_data[field])

    # 4. Helper to update nested relationships
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
            # Create new if it didn't exist
            new_instance = model_class(student_id=db_student.id, **data_dict)
            session.add(new_instance)

    # 5. Apply Nested Updates
    await update_section(StudentAddress, db_student.address, student_in.address)
    await update_section(StudentFamily, db_student.family, student_in.family)
    await update_section(StudentEducation, db_student.education, student_in.education)
    await update_section(StudentHealth, db_student.health, student_in.health)
    await update_section(StudentSpirituality, db_student.spirituality, student_in.spirituality)

    await session.commit()
    return await _fetch_full_student(session, student_id)


# --- 5. DELETE STUDENT ---
@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_student(
    student_id: int,
    current_user: User = Depends(get_current_super_admin),
    session: AsyncSession = Depends(get_session),
):
    """
    Delete a student.
    """
    result = await session.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    await session.delete(student)
    await session.commit()
    
    # Return nothing (None) because status is 204
    return None


# --- HELPER FUNCTION ---
async def _fetch_full_student(session: AsyncSession, student_id: int) -> Optional[Student]:
    """Helper to fetch student with all relationships loaded"""
    query = select(Student).where(Student.id == student_id).options(
        selectinload(Student.address),
        selectinload(Student.family),
        selectinload(Student.education),
        selectinload(Student.health),
        selectinload(Student.spirituality),
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()