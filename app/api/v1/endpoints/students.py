from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
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

router = APIRouter()


@router.post("/", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
async def create_student(
    student_data: StudentCreate,
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

    # Create student
    new_student = Student(
        **student_data.model_dump(),
        created_by_id=current_user.id,
    )
    session.add(new_student)
    await session.commit()
    await session.refresh(new_student)

    return StudentResponse.model_validate(new_student)


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
    for field, value in update_data.items():
        setattr(student, field, value)

    await session.commit()
    await session.refresh(student)

    return StudentResponse.model_validate(student)


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

