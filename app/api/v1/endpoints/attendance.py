from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_session
from app.models.attendance import AttendanceSession, AttendanceRecord, ProgramType as AttendanceType, AttendanceStatus, Program
from app.models.department import Department
from app.models.student import Student, StudentCategory
from app.core.dependencies import require_manager_department_access, get_current_active_user
from app.schemas.attendance import (
    AttendanceSessionCreate,
    AttendanceSessionResponse,
    AttendanceRecordResponse,
    AttendanceRecordCreate,
    AttendanceRecordInput,
    AttendanceBatchCreate,
)
from app.models.user import User
from app.schemas.student import StudentResponse

router = APIRouter()


@router.post("/sessions/", response_model=AttendanceSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_attendance_session(
    session_data: AttendanceSessionCreate,
    current_user_and_session: tuple[User, AsyncSession] = Depends(require_manager_department_access),
):
    """Create an attendance session and optional initial records. Managers/Admins for the department can create."""
    current_user, session = current_user_and_session

    # Validate department
    result = await session.execute(select(Department).where(Department.id == session_data.department_id))
    dept = result.scalar_one_or_none()
    if not dept:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")

    # normalize category value (allow either enum or str)
    cat = session_data.category
    if hasattr(cat, "value"):
        cat_val = cat.value
    else:
        cat_val = cat

    new_session = AttendanceSession(
        date=session_data.date,
        department_id=session_data.department_id,
        target_category=cat_val,
        type=session_data.type,
        created_by_id=current_user.id,
    )
    session.add(new_session)
    await session.flush()

    # Build initial records: if `records` provided, use their values, otherwise
    # create a AttendanceRecord for every student in the department+category
    records = []

    # Collect provided overrides
    provided_map = {}
    if session_data.records:
        for r in session_data.records:
            provided_map[r.student_id] = {"present": r.present, "notes": r.notes}

    # Query all students in the department with matching category
    students_q = select(Student).where(
        Student.department_id == session_data.department_id,
        Student.category == cat_val,
    )
    result = await session.execute(students_q)
    students = result.scalars().all()

    for s in students:
        if s.id in provided_map:
            p = provided_map[s.id]
            status = AttendanceStatus.PRESENT if p.get("present", False) else AttendanceStatus.ABSENT
            rec = AttendanceRecord(session_id=new_session.id, student_id=s.id, status=status, remarks=p.get("notes"))
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


@router.get("/eligible-students/", response_model=List[StudentResponse])
async def eligible_students(
    department_id: int = Query(..., description="Department id"),
    category: StudentCategory = Query(..., description="StudentCategory"),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """Return students eligible for attendance checklist for the department + category."""
    q = select(Student).where(Student.department_id == department_id, Student.category == (category.value if hasattr(category, 'value') else category))
    res = await session.execute(q)
    students = res.scalars().all()
    return students


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


@router.get("/sessions/{session_id}", response_model=AttendanceSessionResponse)
async def get_session(session_id: int, current_user: User = Depends(get_current_active_user), session: AsyncSession = Depends(get_session)):
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


from app.schemas.attendance import AttendanceRecordCreate


@router.post("/sessions/{session_id}/records/", response_model=AttendanceRecordResponse, status_code=status.HTTP_201_CREATED)
async def add_record(session_id: int, record: AttendanceRecordCreate, current_user_and_session: tuple[User, AsyncSession] = Depends(require_manager_department_access)):
    current_user, session = current_user_and_session

    # validate session exists
    result = await session.execute(select(AttendanceSession).where(AttendanceSession.id == session_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    status_val = AttendanceStatus.PRESENT if record.present else AttendanceStatus.ABSENT
    new = AttendanceRecord(session_id=session_id, student_id=record.student_id, status=status_val, remarks=record.notes)
    session.add(new)
    await session.commit()
    await session.refresh(new)
    return AttendanceRecordResponse(id=new.id, student_id=new.student_id, status=new.status, remarks=new.remarks)


@router.post("/sessions/batch", status_code=status.HTTP_201_CREATED)
async def create_attendance_batch(
    data: AttendanceBatchCreate,
    current_user_and_session: tuple[User, AsyncSession] = Depends(require_manager_department_access),
):
    """Create attendance for an entire category in a department on a date (batch mode).
    - Finds or creates a Program for the department and type
    - Creates a Session tied to that Program + target_category if not present
    - Bulk creates AttendanceRecord entries for the supplied student records
    """
    current_user, session = current_user_and_session

    # Find or create Program
    q = select(Program).where(Program.department_id == data.department_id, Program.type == data.type)
    res = await session.execute(q)
    program = res.scalar_one_or_none()
    if not program:
        program = Program(name=f"{data.type.value.title()} Program", department_id=data.department_id, type=data.type, description=f"Default {data.type.value} container")
        session.add(program)
        await session.flush()
        await session.refresh(program)

    # Check duplicate: Program + date + target_category
    existing_q = select(AttendanceSession).where(
        AttendanceSession.program_id == program.id,
        AttendanceSession.date == data.date,
        AttendanceSession.target_category == (data.category.value if hasattr(data.category, 'value') else data.category),
    )
    existing = (await session.execute(existing_q)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Attendance already taken for this category on this date.")

    new_session = AttendanceSession(date=data.date, program_id=program.id, department_id=data.department_id, target_category=(data.category.value if hasattr(data.category, 'value') else data.category), type=data.type, created_by_id=current_user.id)
    session.add(new_session)
    await session.flush()

    # Bulk create records
    for r in data.records:
        status_val = AttendanceStatus.PRESENT if r.present else AttendanceStatus.ABSENT
        rec = AttendanceRecord(session_id=new_session.id, student_id=r.student_id, status=status_val, remarks=r.notes)
        session.add(rec)

    await session.commit()
    await session.refresh(new_session)

    return {"status": "success", "session_id": new_session.id, "records_count": len(data.records)}


@router.post("/sessions/{session_id}/collect/", response_model=AttendanceRecordResponse)
async def collect_attendance(session_id: int, record: AttendanceRecordCreate, current_user_and_session: tuple[User, AsyncSession] = Depends(require_manager_department_access)):
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
    new = AttendanceRecord(session_id=session_id, student_id=record.student_id, status=status_val, remarks=record.notes)
    session.add(new)
    await session.commit()
    await session.refresh(new)
    return AttendanceRecordResponse(id=new.id, student_id=new.student_id, status=new.status, remarks=new.remarks)
