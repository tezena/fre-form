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
    
    # Check if the department_id exists in the user's assigned departments
    # Note: This assumes user.departments is loaded. If using async, you might need 
    # to fetch this explicitly if it's not in the session.
    user_dept_ids = [d.id for d in user.departments]
    if department_id not in user_dept_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to manage this department."
        )



# -----------------------------------------------------------------------------
# 1. BATCH CREATE (The one you are using)
# -----------------------------------------------------------------------------
@router.post("/sessions/", status_code=status.HTTP_201_CREATED)
async def create_attendance_batch(
    data: AttendanceBatchCreate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Take attendance for a specific Program.
    """
    # 1. Find the Program explicitly using the ID provided
    program = await session.get(Program, data.program_id)
    if not program:
        raise HTTPException(status_code=404, detail="Program not found. Please select a valid program.")

    # 2. Security: Ensure the user manages the department this program belongs to
    check_department_permission(current_user, program.department_id)

    # Normalize category
    cat_val = data.category.value if hasattr(data.category, 'value') else data.category

    # 3. Check for Duplicates (Did we already take attendance for this group today?)
    existing_q = select(AttendanceSession).where(
        AttendanceSession.program_id == program.id,
        AttendanceSession.date == data.date,
        AttendanceSession.target_category == cat_val,
    )
    existing = (await session.execute(existing_q)).scalar_one_or_none()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Attendance has already been recorded for this category in this program today."
        )

    # 4. Create the Session (Inheriting safely from the Program)
    new_session = AttendanceSession(
        date=data.date, 
        program_id=program.id, 
        department_id=program.department_id,  # Safely copied from database, not frontend
        target_category=cat_val, 
        type=program.type,                    # REGULAR or EVENT safely copied from the program
        created_by_id=current_user.id
    )
    session.add(new_session)
    await session.flush() # Flush to get the new_session.id

    # 5. Bulk Create Records
    records_to_add = []
    for r in data.records:
        # We REMOVED the "status_val = ..." logic because r.status is already correct!
        rec = AttendanceRecord(
            session_id=new_session.id, 
            student_id=r.student_id, 
            status=r.status,  # <--- Use the exact enum the frontend sent
            remarks=r.notes
        )
        records_to_add.append(rec)
    
    session.add_all(records_to_add)
    await session.commit()

    return {
        "status": "success", 
        "session_id": new_session.id, 
        "program_name": program.name,
        "records_count": len(records_to_add)
    }

# -----------------------------------------------------------------------------
# 2. GET ELIGIBLE STUDENTS (For Checklist UI)
# -----------------------------------------------------------------------------


@router.get("/eligible-students/", response_model=List[StudentAttendanceList])
async def eligible_students(
    department_id: int = Query(..., description="Department id"),
    category: StudentCategory = Query(..., description="StudentCategory"),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """Return an optimized, lightweight list of students for the attendance UI."""
    # Normalize category for query
    cat_val = category.value if hasattr(category, 'value') else category
    
    # Just a simple, lightning-fast query. No eager loading needed!
    q = select(Student).where(
        Student.department_id == department_id, 
        Student.category == cat_val
    )
    
    res = await session.execute(q)
    students = res.scalars().all()
    
    return students

# -----------------------------------------------------------------------------
# 4. LIST SESSIONS
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
    # 👇 ADDED: .options(selectinload(...)) to fix MissingGreenlet
    q = select(AttendanceSession).options(selectinload(AttendanceSession.records))
    
    # Filter out deleted sessions unless explicitly requested
    if not include_inactive:
        q = q.where(AttendanceSession.is_active == True)

    if program_id is not None:
        q = q.where(AttendanceSession.program_id == program_id)
    if department_id is not None:
        q = q.where(AttendanceSession.department_id == department_id)
    if category is not None:
        q = q.where(AttendanceSession.target_category == category)

    result = await session.execute(q)
    sessions = result.scalars().all()
    
    out = []
    for s in sessions:
        # 👇 ADDED: Manual mapping to fix the "missing category" error
        out.append(AttendanceSessionResponse(
            id=s.id,
            date=s.date,
            program_id=s.program_id,
            department_id=s.department_id,
            category=s.target_category,  # Map DB field to Schema field
            type=s.type,
            is_active=s.is_active,
            records=s.records or []      # Pass the eagerly loaded records
        ))
        
    return out


# -----------------------------------------------------------------------------
# 3. GET SINGLE SESSION
# -----------------------------------------------------------------------------
@router.get("/sessions/{session_id}", response_model=AttendanceSessionResponse)
async def get_session_details(
    session_id: int, 
    current_user: User = Depends(get_current_active_user), 
    session: AsyncSession = Depends(get_session)
):
    # 👇 ADDED: .options(selectinload(AttendanceSession.records))
    query = select(AttendanceSession).where(
        AttendanceSession.id == session_id
    ).options(selectinload(AttendanceSession.records))
    
    result = await session.execute(query)
    s = result.scalar_one_or_none()
    
    if not s:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
   
    return AttendanceSessionResponse(
        id=s.id,
        date=s.date,
        program_id=s.program_id,       # <-- Added to match your updated schema
        department_id=s.department_id,
        category=s.target_category,
        type=s.type,
        is_active=s.is_active,         # <-- Added to match your updated schema
        records=s.records or [],       # <-- Safe now because we eager-loaded it!
    )


# -----------------------------------------------------------------------------
# 4. COLLECT (Update existing session)
# -----------------------------------------------------------------------------
@router.post("/sessions/{session_id}/collect/", response_model=AttendanceRecordResponse)
async def collect_attendance(
    session_id: int, 
    record: AttendanceRecordCreate, 
    current_user_and_session: tuple[User, AsyncSession] = Depends(require_manager_department_access)
):
    """Mark attendance for an individual student for a session (create if missing)."""
    current_user, session = current_user_and_session

    result = await session.execute(select(AttendanceSession).where(AttendanceSession.id == session_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    res = await session.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.session_id == session_id,
            AttendanceRecord.student_id == record.student_id,
        )
    )
    existing = res.scalar_one_or_none()
    
    if existing:
        # 👇 Updated: Just use record.status directly
        existing.status = record.status
        existing.remarks = record.notes
        await session.commit()
        await session.refresh(existing)
        return existing

    # otherwise create
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


@router.patch("/sessions/{session_id}", response_model=AttendanceSessionResponse)
async def update_attendance_session(
    session_id: int,
    session_data: AttendanceSessionUpdate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Update details of the session itself (e.g., changing the date).
    Does NOT affect the attendance records inside it.
    """
    
    # 1. Fetch the existing session WITH RECORDS (Fixes MissingGreenlet)
    query = select(AttendanceSession).where(
        AttendanceSession.id == session_id
    ).options(selectinload(AttendanceSession.records))
    
    result = await session.execute(query)
    existing_session = result.scalar_one_or_none()
    
    if not existing_session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    # 2. Permission Check
    check_department_permission(current_user, existing_session.department_id)

    # 3. Apply the updates dynamically
    update_data = session_data.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(existing_session, key, value)

    # 4. Save to database
    await session.commit()

    # 5. Return the mapped response (Fixes the "Missing Category" error)
    return AttendanceSessionResponse(
        id=existing_session.id,
        date=existing_session.date,
        program_id=existing_session.program_id,
        department_id=existing_session.department_id,
        category=existing_session.target_category, # <-- Mapped safely
        type=existing_session.type,
        is_active=existing_session.is_active,
        records=existing_session.records or []     # <-- Safe because of selectinload
    )


# -----------------------------------------------------------------------------
# 5. SOFT DELETE SESSION
# -----------------------------------------------------------------------------
@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attendance_session(
    session_id: int,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Soft delete an attendance session. 
    Hides it from standard views but preserves the historical data.
    """
    
    # 1. Fetch existing session
    result = await session.execute(select(AttendanceSession).where(AttendanceSession.id == session_id))
    existing_session = result.scalar_one_or_none()
    
    if not existing_session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    # 2. Verify permission
    check_department_permission(current_user, existing_session.department_id)

    # 3. Soft Delete
    existing_session.is_active = False
    
    await session.commit()
    
    return None