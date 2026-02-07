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
)
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

# -----------------------------------------------------------------------------
# 1. CREATE SESSION (Manual / Standard)
# -----------------------------------------------------------------------------
@router.post("/sessions/", response_model=AttendanceSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_attendance_session(
    session_data: AttendanceSessionCreate,
    current_user: User = Depends(get_current_active_user), # CHANGED: Use basic user dependency
    session: AsyncSession = Depends(get_session),
):
    """Create an attendance session manually."""
    
    # 1. Permission Check
    check_department_permission(current_user, session_data.department_id)

    # 2. Validate department exists
    result = await session.execute(select(Department).where(Department.id == session_data.department_id))
    dept = result.scalar_one_or_none()
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")

    # 3. Normalize category
    cat_val = session_data.category.value if hasattr(session_data.category, "value") else session_data.category

    new_session = AttendanceSession(
        date=session_data.date,
        department_id=session_data.department_id,
        target_category=cat_val,
        type=session_data.type,
        created_by_id=current_user.id,
    )
    session.add(new_session)
    await session.flush()

    # 4. Build Initial Records (Optional)
    records = []
    
    # Create a map of provided overrides (if any)
    provided_map = {}
    if session_data.records:
        for r in session_data.records:
            provided_map[r.student_id] = {"present": r.present, "notes": r.notes}

    # Fetch all students in this category to generate the full list
    students_q = select(Student).where(
        Student.department_id == session_data.department_id,
        Student.category == cat_val,
    )
    result = await session.execute(students_q)
    students = result.scalars().all()

    for s in students:
        if s.id in provided_map:
            p = provided_map[s.id]
            status_val = AttendanceStatus.PRESENT if p.get("present", False) else AttendanceStatus.ABSENT
            rec = AttendanceRecord(session_id=new_session.id, student_id=s.id, status=status_val, remarks=p.get("notes"))
        else:
            rec = AttendanceRecord(session_id=new_session.id, student_id=s.id, status=AttendanceStatus.ABSENT)
        session.add(rec)
        records.append(rec)

    await session.commit()
    await session.refresh(new_session)

    return AttendanceSessionResponse(
        id=new_session.id,
        date=new_session.date,
        department_id=new_session.department_id,
        category=new_session.target_category,
        type=new_session.type,
        records=records,
    )

# -----------------------------------------------------------------------------
# 2. BATCH CREATE (The one you are using)
# -----------------------------------------------------------------------------
@router.post("/sessions/batch", status_code=status.HTTP_201_CREATED)
async def create_attendance_batch(
    data: AttendanceBatchCreate,
    current_user: User = Depends(get_current_active_user), # CHANGED: Fixed dependency issue
    session: AsyncSession = Depends(get_session),
):
    """
    Create attendance for an entire category in a department on a date (batch mode).
    - Checks Permissions manually
    - Finds/Creates Program
    - Creates Session
    - Bulk Creates Records
    """
    
    # 1. Permission Check
    check_department_permission(current_user, data.department_id)

    # 2. Find or create Program
    q = select(Program).where(Program.department_id == data.department_id, Program.type == data.type)
    res = await session.execute(q)
    program = res.scalar_one_or_none()
    
    if not program:
        # Auto-create default program
        program = Program(
            name=f"{data.type.value.title()} Program", 
            department_id=data.department_id, 
            type=data.type, 
            description=f"Default {data.type.value} container"
        )
        session.add(program)
        await session.flush()
        await session.refresh(program)

    # 3. Normalize Category
    cat_val = data.category.value if hasattr(data.category, 'value') else data.category

    # 4. Check for Duplicate Session
    existing_q = select(AttendanceSession).where(
        AttendanceSession.program_id == program.id,
        AttendanceSession.date == data.date,
        AttendanceSession.target_category == cat_val,
    )
    existing = (await session.execute(existing_q)).scalar_one_or_none()
    
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Attendance already taken for this category on this date.")

    # 5. Create Session
    new_session = AttendanceSession(
        date=data.date, 
        program_id=program.id, 
        department_id=data.department_id, 
        target_category=cat_val, 
        type=data.type, 
        created_by_id=current_user.id
    )
    session.add(new_session)
    await session.flush()

    # 6. Bulk Create Records
    for r in data.records:
        status_val = AttendanceStatus.PRESENT if r.present else AttendanceStatus.ABSENT
        rec = AttendanceRecord(
            session_id=new_session.id, 
            student_id=r.student_id, 
            status=status_val, 
            remarks=r.notes
        )
        session.add(rec)

    await session.commit()
    await session.refresh(new_session)

    return {"status": "success", "session_id": new_session.id, "records_count": len(data.records)}

# -----------------------------------------------------------------------------
# 3. GET ELIGIBLE STUDENTS (For Checklist UI)
# -----------------------------------------------------------------------------
@router.get("/eligible-students/", response_model=List[StudentResponse])
async def eligible_students(
    department_id: int = Query(..., description="Department id"),
    category: StudentCategory = Query(..., description="StudentCategory"),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """Return students eligible for attendance checklist for the department + category."""
    # Normalize category for query
    cat_val = category.value if hasattr(category, 'value') else category
    
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
    department_id: Optional[int] = Query(None),
    category: Optional[str] = Query(None),
    type: Optional[AttendanceType] = Query(None),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    q = select(AttendanceSession)
    if department_id is not None:
        q = q.where(AttendanceSession.department_id == department_id)
    if category is not None:
        q = q.where(AttendanceSession.target_category == category)
    if type is not None:
        q = q.where(AttendanceSession.type == type)

    result = await session.execute(q)
    sessions = result.scalars().all()
    
    out = []
    for s in sessions:
        # We might need to refresh to load lazy relationships if not eager loaded
        await session.refresh(s) 
        out.append(AttendanceSessionResponse(
            id=s.id,
            date=s.date,
            department_id=s.department_id,
            category=s.target_category,
            type=s.type,
            records=s.records or [],
        ))
    return out

# -----------------------------------------------------------------------------
# 5. GET SINGLE SESSION
# -----------------------------------------------------------------------------
@router.get("/sessions/{session_id}", response_model=AttendanceSessionResponse)
async def get_session_details(
    session_id: int, 
    current_user: User = Depends(get_current_active_user), 
    session: AsyncSession = Depends(get_session)
):
    result = await session.execute(select(AttendanceSession).where(AttendanceSession.id == session_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    await session.refresh(s)
    return AttendanceSessionResponse(
        id=s.id,
        date=s.date,
        department_id=s.department_id,
        category=s.target_category,
        type=s.type,
        records=s.records or [],
    )

# -----------------------------------------------------------------------------
# 6. ADD SINGLE RECORD (Late Arrival)
# -----------------------------------------------------------------------------
@router.post("/sessions/{session_id}/records/", response_model=AttendanceRecordResponse, status_code=status.HTTP_201_CREATED)
async def add_record(
    session_id: int, 
    record: AttendanceRecordCreate, 
    # Use tuple unpacking for dependencies that return (User, Session)
    # Note: require_manager... works here because session_id is in the PATH, not body
    current_user_and_session: tuple[User, AsyncSession] = Depends(require_manager_department_access)
):
    current_user, session = current_user_and_session

    # validate session exists
    result = await session.execute(select(AttendanceSession).where(AttendanceSession.id == session_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    status_val = AttendanceStatus.PRESENT if record.present else AttendanceStatus.ABSENT
    new = AttendanceRecord(
        session_id=session_id, 
        student_id=record.student_id, 
        status=status_val, 
        remarks=record.notes
    )
    session.add(new)
    await session.commit()
    await session.refresh(new)
    return AttendanceRecordResponse(id=new.id, student_id=new.student_id, status=new.status, remarks=new.remarks)

# -----------------------------------------------------------------------------
# 7. COLLECT (Update existing session)
# -----------------------------------------------------------------------------
@router.post("/sessions/{session_id}/collect/", response_model=AttendanceRecordResponse)
async def collect_attendance(
    session_id: int, 
    record: AttendanceRecordCreate, 
    current_user_and_session: tuple[User, AsyncSession] = Depends(require_manager_department_access)
):
    """Mark attendance for an individual student for a session (create if missing)."""
    current_user, session = current_user_and_session

    # validate session exists
    result = await session.execute(select(AttendanceSession).where(AttendanceSession.id == session_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    # map incoming present -> status
    status_val = AttendanceStatus.PRESENT if record.present else AttendanceStatus.ABSENT

    # find existing record
    res = await session.execute(
        select(AttendanceRecord).where(
            AttendanceRecord.session_id == session_id,
            AttendanceRecord.student_id == record.student_id,
        )
    )
    existing = res.scalar_one_or_none()
    
    if existing:
        existing.status = status_val
        existing.remarks = record.notes
        await session.commit()
        await session.refresh(existing)
        return AttendanceRecordResponse(id=existing.id, student_id=existing.student_id, status=existing.status, remarks=existing.remarks)

    # otherwise create
    new = AttendanceRecord(
        session_id=session_id, 
        student_id=record.student_id, 
        status=status_val, 
        remarks=record.notes
    )
    session.add(new)
    await session.commit()
    await session.refresh(new)
    return AttendanceRecordResponse(id=new.id, student_id=new.student_id, status=new.status, remarks=new.remarks)