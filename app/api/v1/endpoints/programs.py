from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_session
from app.models.attendance import (
    AttendanceSession, 
    AttendanceRecord, 
    ProgramType as AttendanceType, 
    AttendanceStatus, 
    Program
)
from app.models.department import Department
from app.models.student import Student, StudentCategory
from app.models.user import User, UserRole
from app.core.dependencies import get_current_active_user, require_manager_department_access

from app.schemas.program import ProgramCreate, ProgramResponse, ProgramUpdate
from app.schemas.student import StudentResponse

router = APIRouter()

# -----------------------------------------------------------------------------
# HELPER: Permission Check
# -----------------------------------------------------------------------------
def check_department_permission(user: User, department_id: int):
    """
    Helper to verify if a user has access to a specific department.
    Super Admins can access all. 
    Admins/Managers must be assigned to the department.
    """
    if user.role == UserRole.SUPER_ADMIN:
        return True
    
    user_dept_ids = [d.id for d in getattr(user, "departments", [])]
    if department_id not in user_dept_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to manage this department."
        )

# =============================================================================
# A. PROGRAM MANAGEMENT
# =============================================================================

@router.post("/programs/", response_model=ProgramResponse, status_code=status.HTTP_201_CREATED)
async def create_program(
    program_data: ProgramCreate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    check_department_permission(current_user, program_data.department_id)

    dept = await session.get(Department, program_data.department_id)
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")

    new_program = Program(**program_data.model_dump())
    session.add(new_program)
    await session.commit()
    await session.refresh(new_program)
    return new_program

@router.get("/programs/", response_model=List[ProgramResponse])
async def list_programs(
    department_id: int = Query(..., description="Filter by department"),
    include_inactive: bool = Query(False, description="Set to true to see archived programs"),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    check_department_permission(current_user, department_id)

    query = select(Program).where(Program.department_id == department_id)
    if not include_inactive:
        query = query.where(Program.is_active == True)
        
    result = await session.execute(query)
    return result.scalars().all()

@router.patch("/programs/{program_id}", response_model=ProgramResponse)
async def update_program(
    program_id: int,
    program_data: ProgramUpdate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    program = await session.get(Program, program_id)
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")

    check_department_permission(current_user, program.department_id)

    update_dict = program_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(program, key, value)

    await session.commit()
    await session.refresh(program)
    return program

@router.delete("/programs/{program_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_program(
    program_id: int,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    program = await session.get(Program, program_id)
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")

    check_department_permission(current_user, program.department_id)
    program.is_active = False
    await session.commit()
    return None