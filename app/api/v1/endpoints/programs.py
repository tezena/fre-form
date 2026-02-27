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
    
    # Check if the department_id exists in the user's assigned departments
    # Note: This assumes user.departments is loaded. If using async, you might need 
    # to fetch this explicitly if it's not in the session.
    user_dept_ids = [d.id for d in user.departments]
    if department_id not in user_dept_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to manage this department."
        )



# ==========================================
# A. PROGRAM MANAGEMENT
# ==========================================

@router.post("/programs/", response_model=ProgramResponse, status_code=status.HTTP_201_CREATED)
async def create_program(
    program_data: ProgramCreate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """Admin creates a new Program (Regular or Event) in their Department."""
    
    # 1. Verify user can manage this department
    check_department_permission(current_user, program_data.department_id)

    # 2. Verify Department exists
    dept = await session.get(Department, program_data.department_id)
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")

    # 3. Create Program
    new_program = Program(**program_data.model_dump())
    session.add(new_program)
    await session.commit()
    await session.refresh(new_program)

    return new_program

@router.patch("/programs/{program_id}", response_model=ProgramResponse)
async def update_program(
    program_id: int,
    program_data: ProgramUpdate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """Update a program's details (Name, Type, or Description)."""
    
    # 1. Fetch existing program
    program = await session.get(Program, program_id)
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")

    # 2. Verify permission (Does this user manage this program's department?)
    check_department_permission(current_user, program.department_id)

    # 3. Apply updates dynamically (only updates fields that were actually sent)
    update_dict = program_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(program, key, value)

    await session.commit()
    await session.refresh(program)

    return program

@router.get("/programs/", response_model=List[ProgramResponse])
async def list_programs(
    department_id: int = Query(..., description="Filter by department"),
    include_inactive: bool = Query(False, description="Set to true to see archived programs"),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """Get programs for a department. Hides archived programs by default."""
    
    check_department_permission(current_user, department_id)

    query = select(Program).where(Program.department_id == department_id)
    
    # Hide soft-deleted programs unless specifically requested
    if not include_inactive:
        query = query.where(Program.is_active == True)
        
    result = await session.execute(query)
    return result.scalars().all()




@router.delete("/programs/{program_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_program(
    program_id: int,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Soft delete a program. 
    It will be archived and hidden, but historical attendance is preserved.
    """
    program = await session.get(Program, program_id)
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")

    check_department_permission(current_user, program.department_id)

    # Perform the Soft Delete
    program.is_active = False
    
    await session.commit()
    
    return None

