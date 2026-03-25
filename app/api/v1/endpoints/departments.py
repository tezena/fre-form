from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_session
from app.models.department import Department
from app.core.dependencies import get_current_super_admin
from app.schemas.department import DepartmentCreate, DepartmentUpdate, DepartmentResponse

router = APIRouter()

@router.post("/", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
async def create_department(
    department_data: DepartmentCreate,
    current_user = Depends(get_current_super_admin),
    session: AsyncSession = Depends(get_session),
):
    """Create a new department. Only Super Admin can create departments."""
    # Check if name already exists
    result = await session.execute(
        select(Department).where(Department.name == department_data.name)
    )
    existing_dept = result.scalar_one_or_none()
    if existing_dept:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Department name already exists"
        )

    # 👇 UPDATED: Use model_dump to capture the new FLS rules (is_profile_builder, allowed_fields)
    new_department = Department(**department_data.model_dump())
    
    session.add(new_department)
    await session.commit()
    await session.refresh(new_department)

    return DepartmentResponse.model_validate(new_department)


@router.get("/", response_model=List[DepartmentResponse])
async def list_departments(
    # 👇 UPDATED: Locked down to Super Admin only
    current_user = Depends(get_current_super_admin),
    session: AsyncSession = Depends(get_session),
):
    """List all departments. Only Super Admin can view departments."""
    result = await session.execute(select(Department))
    departments = result.scalars().all()
    return [DepartmentResponse.model_validate(dept) for dept in departments]


@router.get("/{department_id}", response_model=DepartmentResponse)
async def get_department(
    department_id: int,
    # 👇 UPDATED: Locked down to Super Admin only
    current_user = Depends(get_current_super_admin),
    session: AsyncSession = Depends(get_session),
):
    """Get a specific department. Only Super Admin can view departments."""
    result = await session.execute(
        select(Department).where(Department.id == department_id)
    )
    department = result.scalar_one_or_none()

    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )

    return DepartmentResponse.model_validate(department)


@router.put("/{department_id}", response_model=DepartmentResponse)
async def update_department(
    department_id: int,
    department_update: DepartmentUpdate,
    current_user = Depends(get_current_super_admin),
    session: AsyncSession = Depends(get_session),
):
    """Update a department. Only Super Admin can update departments."""
    result = await session.execute(
        select(Department).where(Department.id == department_id)
    )
    department = result.scalar_one_or_none()

    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )

    # Check if new name conflicts
    if department_update.name and department_update.name != department.name:
        result = await session.execute(
            select(Department).where(Department.name == department_update.name)
        )
        existing_dept = result.scalar_one_or_none()
        if existing_dept:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Department name already exists"
            )

    # Update fields dynamically (this automatically handles the new fields correctly)
    update_data = department_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(department, field, value)

    await session.commit()
    await session.refresh(department)

    return DepartmentResponse.model_validate(department)


@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_department(
    department_id: int,
    current_user = Depends(get_current_super_admin),
    session: AsyncSession = Depends(get_session),
):
    """Delete a department. Only Super Admin can delete departments."""
    result = await session.execute(
        select(Department).where(Department.id == department_id)
    )
    department = result.scalar_one_or_none()

    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )

    await session.delete(department)
    await session.commit()
    return None