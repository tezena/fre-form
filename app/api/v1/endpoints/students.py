from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_session
from app.models.student import Student
from app.models.department import Department
from app.models.user import User, UserRole
from app.core.dependencies import (
    get_current_active_user,
    get_current_super_admin,
    require_manager_department_access,
    get_user_departments,
    check_admin_department_access,
)
from app.schemas.student import StudentCreate, StudentUpdate, StudentResponse

student_examples = {
    "1_Child": {
        "summary": "Category: Children",
        "value": {
            "name": "Little Caleb",
            "age": 8,
            "sex": "M",
            "church": "St. Mary",
            "department_id": 1,
            "category": "CHILDREN",
            "category_details": {
                "child": {
                    "photo_url": "",
                    "category": "CHILDREN",
                    "parentName": "Sarah Connor",
                    "parentPhone": "+251911223344",
                    "grade": "2nd Grade",
                    "schoolName": "Future Hope Academy"
                }
            }
        }
    },
    "2_Adult": {
        "summary": "Category: Adult",
        "value": {
            "name": "Abebe Bikila",
            "age": 35,
            "sex": "M",
            "church": "Medhane Alem",
            "department_id": 1,
            "category": "ADULT",
            "category_details": {
                "Adult": {
                    "photo_url": "",
                    "category": "ADULT",
                    "phone": "+251911998877",
                    "email": "abebe@example.com",
                    "maritalStatus": "Married",
                    "occupation": "Engineer",
                    "education": "BSc"
                }
            }
        }
    },
    "3_Youth": {
        "summary": "Category: Youth",
        "value": {
            "name": "Lydia Tadesse",
            "age": 22,
            "sex": "F",
            "church": "Trinity",
            "department_id": 1,
            "category": "YOUTH",
            "category_details": {
                "youth": {
                    "photo_url": "",
                    "category": "YOUTH",
                    "phone": "+251911556677",
                    "education": "University Student",
                    "occupation": "Student"
                }
            }
        }
    }
}

router = APIRouter()


@router.post("/", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
async def create_student(
    student_data: StudentCreate = Body(..., examples=student_examples),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Create a new student.
    - Super Admin: Can create students in any department
    - Admin: Can create students only in their assigned departments
    - Manager: Can create students only in their assigned departments
    """
    # Validate department exists
    result = await session.execute(
        select(Department).where(Department.id == student_data.department_id)
    )
    department = result.scalar_one_or_none()
    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )

    # Check permissions
    if current_user.role != UserRole.SUPER_ADMIN:
        has_access = await check_admin_department_access(
            current_user, student_data.department_id, session
        )
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User does not have access to department {student_data.department_id}"
            )

    # Create student: extract nested profile and store in `profile_data`
    payload = student_data.model_dump()
    category_details = payload.pop("category_details", None) or {}

    # Top-level fields we store directly
    top_level_fields = {"name", "age", "church", "sex", "department_id", "category"}
    student_kwargs = {k: v for k, v in payload.items() if k in top_level_fields}

    # Extract the nested object that matches the selected category
    nested = None
    cat = student_kwargs.get("category")
    # normalize enum vs string
    if hasattr(cat, "value"):
        cat = cat.value

    if cat == "CHILDREN":
        nested = category_details.get("child")
    elif cat == "ADOLESCENT":
        nested = category_details.get("Adolescent")
    elif cat == "YOUTH":
        nested = category_details.get("youth")
    elif cat == "ADULT":
        nested = category_details.get("Adult")

    new_student = Student(
        **student_kwargs,
        profile_data=nested,
        created_by_id=current_user.id,
    )
    session.add(new_student)
    await session.commit()
    await session.refresh(new_student)

    return StudentResponse.model_validate(new_student)


@router.put("/{student_id}", response_model=StudentResponse)
async def update_student(
    student_id: int,
    student_update: StudentUpdate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Update a student.
    - Super Admin: Can update any student
    - Admin/Manager: Can update students only in their assigned departments
    """
    result = await session.execute(
        select(Student).where(Student.id == student_id)
    )
    student = result.scalar_one_or_none()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )

    # Check permissions for current department
    if current_user.role != UserRole.SUPER_ADMIN:
        has_access = await check_admin_department_access(
            current_user, student.department_id, session
        )
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not have access to this student's department"
            )

    # If updating department_id, check permissions for new department
    if student_update.department_id is not None:
        if current_user.role != UserRole.SUPER_ADMIN:
            has_access = await check_admin_department_access(
                current_user, student_update.department_id, session
            )
            if not has_access:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"User does not have access to department {student_update.department_id}"
                )

    # Update fields
    update_data = student_update.model_dump(exclude_unset=True)

    # If category_details provided, merge the nested object for the selected category
    if "category_details" in update_data:
        new_details = update_data.pop("category_details") or {}
        cat = student_update.category or student.category
        # normalize enum vs string
        if hasattr(cat, "value"):
            cat = cat.value

        nested_key = None
        if cat == "CHILDREN":
            nested_key = "child"
        elif cat == "ADOLESCENT":
            nested_key = "Adolescent"
        elif cat == "YOUTH":
            nested_key = "youth"
        elif cat == "ADULT":
            nested_key = "Adult"

        new_profile = new_details.get(nested_key) if nested_key else None
        if new_profile is not None:
            # create a new dict instance so SQLAlchemy detects the change
            existing = dict(student.profile_data or {})
            existing.update(new_profile)
            student.profile_data = existing

    for field, value in update_data.items():
        setattr(student, field, value)

    await session.commit()
    await session.refresh(student)

    return StudentResponse.model_validate(student)


@router.get("/", response_model=List[StudentResponse])
async def list_students(
    department_id: int = Query(None, description="Filter by department ID"),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """
    List students.
    - Super Admin: Can view all students
    - Admin: Can view students only in their assigned departments
    - Manager: Can view students only in their assigned departments
    """
    query = select(Student)

    if current_user.role == UserRole.SUPER_ADMIN:
        # Super Admin can see all students
        if department_id:
            query = query.where(Student.department_id == department_id)
    else:
        # Admin and Manager can only see students in their departments
        user_departments = await get_user_departments(current_user.id, session)
        if not user_departments:
            return []

        query = query.where(Student.department_id.in_(user_departments))
        if department_id:
            if department_id not in user_departments:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"User does not have access to department {department_id}"
                )
            query = query.where(Student.department_id == department_id)

    result = await session.execute(query)
    students = result.scalars().all()
    return [StudentResponse.model_validate(student) for student in students]


@router.get("/{student_id}", response_model=StudentResponse)
async def get_student(
    student_id: int,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Get a specific student.
    - Super Admin: Can view any student
    - Admin/Manager: Can view students only in their assigned departments
    """
    result = await session.execute(
        select(Student).where(Student.id == student_id)
    )
    student = result.scalar_one_or_none()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )

    # Check permissions
    if current_user.role != UserRole.SUPER_ADMIN:
        has_access = await check_admin_department_access(
            current_user, student.department_id, session
        )
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not have access to this student's department"
            )

    return StudentResponse.model_validate(student)


# Duplicate update endpoint removed; the update logic above handles merging of nested `category_details`.

@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_student(
    student_id: int,
    current_user: User = Depends(get_current_super_admin),
    session: AsyncSession = Depends(get_session),
):
    """
    Delete a student. Only Super Admin can delete students.
    """
    result = await session.execute(
        select(Student).where(Student.id == student_id)
    )
    student = result.scalar_one_or_none()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )

    await session.delete(student)
    await session.commit()
    return None

