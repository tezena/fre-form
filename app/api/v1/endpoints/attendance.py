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
from app.schemas.attendance import (
    AttendanceSessionCreate,
    AttendanceSessionResponse,
    AttendanceRecordResponse,
    AttendanceRecordCreate,
    AttendanceBatchCreate,
    StudentAttendanceList, 
    AttendanceSessionUpdate

)
from app.schemas.program import ProgramCreate, ProgramResponse, ProgramUpdate
from app.schemas.student import StudentResponse
from sqlalchemy.orm import selectinload


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



#=============================================================================
# B. ATTENDANCE SESSIONS & RECORDS
# =============================================================================

# -----------------------------------------------------------------------------
# 1. BATCH CREATE
# -----------------------------------------------------------------------------
@router.post("/sessions/", status_code=status.HTTP_201_CREATED)
async def create_attendance_batch(
    data: AttendanceBatchCreate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    program = await session.get(Program, data.program_id)
    if not program:
        raise HTTPException(status_code=404, detail="Program not found.")

    check_department_permission(current_user, program.department_id)
    cat_val = data.category.value if hasattr(data.category, 'value') else data.category

    existing_q = select(AttendanceSession).where(
        AttendanceSession.program_id == program.id,
        AttendanceSession.date == data.date,
        AttendanceSession.target_category == cat_val,
    )
    if (await session.execute(existing_q)).scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Attendance already recorded for this category today.")

    new_session = AttendanceSession(
        date=data.date, 
        program_id=program.id, 
        department_id=program.department_id,
        target_category=cat_val, 
        type=program.type,
        created_by_id=current_user.id
    )
    session.add(new_session)
    await session.flush()

    records_to_add = [
        AttendanceRecord(
            session_id=new_session.id, 
            student_id=r.student_id, 
            status=r.status, 
            remarks=r.notes
        ) for r in data.records
    ]
    session.add_all(records_to_add)
    await session.commit()

    return {
        "status": "success", 
        "session_id": new_session.id, 
        "program_name": program.name,
        "records_count": len(records_to_add)
    }

# -----------------------------------------------------------------------------
# 2. GET ELIGIBLE STUDENTS 
# -----------------------------------------------------------------------------
@router.get("/eligible-students/", response_model=List[StudentAttendanceList])
async def eligible_students(
    department_id: int = Query(..., description="Department id"),
    category: StudentCategory = Query(..., description="StudentCategory"),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    # SECURITY CHECK
    check_department_permission(current_user, department_id)

    cat_val = category.value if hasattr(category, 'value') else category
    q = select(Student).where(Student.department_id == department_id, Student.category == cat_val)
    
    res = await session.execute(q)
    return res.scalars().all()

# -----------------------------------------------------------------------------
# 3. LIST SESSIONS
# -----------------------------------------------------------------------------
@router.get("/sessions/", response_model=List[AttendanceSessionResponse])
async def list_attendance_sessions(
    program_id: Optional[int] = Query(None, description="Filter by Program"),
    department_id: Optional[int] = Query(None),
    category: Optional[str] = Query(None),
    include_inactive: bool = Query(False, description="Set to true to see deleted sessions"),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    q = select(AttendanceSession).options(selectinload(AttendanceSession.records))
    
    if not include_inactive:
        q = q.where(AttendanceSession.is_active == True)

    # SECURITY FILTER
    if current_user.role != UserRole.SUPER_ADMIN:
        allowed_dept_ids = [d.id for d in getattr(current_user, "departments", [])]
        if department_id is not None:
            if department_id not in allowed_dept_ids:
                raise HTTPException(status_code=403, detail="Not authorized for this department")
            q = q.where(AttendanceSession.department_id == department_id)
        else:
            q = q.where(AttendanceSession.department_id.in_(allowed_dept_ids))
    else:
        if department_id is not None:
            q = q.where(AttendanceSession.department_id == department_id)

    if program_id is not None:
        q = q.where(AttendanceSession.program_id == program_id)
    if category is not None:
        q = q.where(AttendanceSession.target_category == category)

    result = await session.execute(q)
    sessions = result.scalars().all()
    
    out = []
    for s in sessions:
        out.append(AttendanceSessionResponse(
            id=s.id,
            date=s.date,
            program_id=s.program_id,
            department_id=s.department_id,
            category=s.target_category, 
            type=s.type,
            is_active=s.is_active,
            records=s.records or [] 
        ))
    return out

# -----------------------------------------------------------------------------
# 4. GET SINGLE SESSION
# -----------------------------------------------------------------------------
@router.get("/sessions/{session_id}", response_model=AttendanceSessionResponse)
async def get_session_details(
    session_id: int, 
    current_user: User = Depends(get_current_active_user), 
    session: AsyncSession = Depends(get_session)
):
    query = select(AttendanceSession).where(
        AttendanceSession.id == session_id
    ).options(selectinload(AttendanceSession.records))
    
    result = await session.execute(query)
    s = result.scalar_one_or_none()
    
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
   
    # SECURITY CHECK
    check_department_permission(current_user, s.department_id)

    return AttendanceSessionResponse(
        id=s.id,
        date=s.date,
        program_id=s.program_id,       
        department_id=s.department_id,
        category=s.target_category,
        type=s.type,
        is_active=s.is_active,         
        records=s.records or [],       
    )

# -----------------------------------------------------------------------------
# 5. COLLECT (Upsert existing session record)
# -----------------------------------------------------------------------------
@router.post("/sessions/{session_id}/collect/", response_model=AttendanceRecordResponse)
async def collect_attendance(
    session_id: int, 
    record: AttendanceRecordCreate, 
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session)
):
    result = await session.execute(select(AttendanceSession).where(AttendanceSession.id == session_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")

    # SECURITY CHECK
    check_department_permission(current_user, s.department_id)

    res = await session.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.session_id == session_id,
            AttendanceRecord.student_id == record.student_id,
        )
    )
    existing = res.scalar_one_or_none()
    
    if existing:
        existing.status = record.status
        existing.remarks = record.notes
        await session.commit()
        await session.refresh(existing)
        return existing

    new = AttendanceRecord(
        session_id=session_id, 
        student_id=record.student_id, 
        status=record.status, 
        remarks=record.notes
    )
    session.add(new)
    await session.commit()
    await session.refresh(new)
    return new

# -----------------------------------------------------------------------------
# 6. UPDATE SESSION (Metadata)
# -----------------------------------------------------------------------------
@router.patch("/sessions/{session_id}", response_model=AttendanceSessionResponse)
async def update_attendance_session(
    session_id: int,
    session_data: AttendanceSessionUpdate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    query = select(AttendanceSession).where(
        AttendanceSession.id == session_id
    ).options(selectinload(AttendanceSession.records))
    
    result = await session.execute(query)
    existing_session = result.scalar_one_or_none()
    
    if not existing_session:
        raise HTTPException(status_code=404, detail="Session not found")

    # SECURITY CHECK
    check_department_permission(current_user, existing_session.department_id)

    update_data = session_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(existing_session, key, value)

    await session.commit()

    return AttendanceSessionResponse(
        id=existing_session.id,
        date=existing_session.date,
        program_id=existing_session.program_id,
        department_id=existing_session.department_id,
        category=existing_session.target_category,
        type=existing_session.type,
        is_active=existing_session.is_active,
        records=existing_session.records or []
    )

# -----------------------------------------------------------------------------
# 7. SOFT DELETE SESSION
# -----------------------------------------------------------------------------
@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attendance_session(
    session_id: int,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(AttendanceSession).where(AttendanceSession.id == session_id))
    existing_session = result.scalar_one_or_none()
    
    if not existing_session:
        raise HTTPException(status_code=404, detail="Session not found")

    # SECURITY CHECK
    check_department_permission(current_user, existing_session.department_id)

    existing_session.is_active = False
    await session.commit()
    
    return None