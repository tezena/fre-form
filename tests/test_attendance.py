import pytest
from datetime import date
from app.models.department import Department
from app.models.student import Student, StudentCategory


@pytest.mark.anyio
async def test_attendance_session_create_and_list(client, async_session):
    # create department and students
    dept = Department(name="Attend Dept")
    async_session.add(dept)
    await async_session.commit()
    await async_session.refresh(dept)

    # create student in department
    s1 = Student(name="Child A", age=8, sex="M", church="C1", department_id=dept.id, category=StudentCategory.CHILDREN)
    s2 = Student(name="Child B", age=9, sex="F", church="C1", department_id=dept.id, category=StudentCategory.CHILDREN)
    async_session.add_all([s1, s2])
    await async_session.commit()
    await async_session.refresh(s1)
    await async_session.refresh(s2)

    # create session without records and expect auto-created records for both students
    payload = {
        "date": str(date.today()),
        "department_id": dept.id,
        "category": "CHILDREN",
        "type": "REGULAR",
    }

    r = await client.post("/api/v1/attendance/sessions/", json=payload)
    assert r.status_code == 201, r.text
    s = r.json()
    assert s["department_id"] == dept.id
    # both students should have default records
    assert len(s["records"]) == 2

    # now collect attendance for student 2
    collect_payload = {"student_id": s2.id, "present": True}
    rcollect = await client.post(f"/api/v1/attendance/sessions/{s['id']}/collect/", json=collect_payload)
    assert rcollect.status_code == 200
    rec = rcollect.json()
    assert rec["student_id"] == s2.id and rec["status"] == "PRESENT"

    # eligible students endpoint
    rel = await client.get(f"/api/v1/attendance/eligible-students/?department_id={dept.id}&category=CHILDREN")
    assert rel.status_code == 200
    elig = rel.json()
    assert len(elig) == 2

    # list
    rlist = await client.get(f"/api/v1/attendance/sessions/?department_id={dept.id}")
    assert rlist.status_code == 200
    items = rlist.json()
    assert any(sess["id"] == s["id"] for sess in items)


@pytest.mark.anyio
async def test_attendance_batch_creates_program_and_session(client, async_session):
    from app.models.attendance import Program
    from sqlalchemy import select

    # create department and students
    dept = Department(name="Batch Dept")
    async_session.add(dept)
    await async_session.commit()
    await async_session.refresh(dept)

    s1 = Student(name="Batch Child A", age=8, sex="M", church="C1", department_id=dept.id, category=StudentCategory.CHILDREN)
    s2 = Student(name="Batch Child B", age=9, sex="F", church="C1", department_id=dept.id, category=StudentCategory.CHILDREN)
    async_session.add_all([s1, s2])
    await async_session.commit()
    await async_session.refresh(s1)
    await async_session.refresh(s2)

    payload = {
        "date": str(date.today()),
        "department_id": dept.id,
        "category": "CHILDREN",
        "type": "REGULAR",
        "records": [
            {"student_id": s1.id, "present": True},
            {"student_id": s2.id, "present": False},
        ],
    }

    r = await client.post("/api/v1/attendance/sessions/batch", json=payload)
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["records_count"] == 2

    # program should exist for department
    res = await async_session.execute(select(Program).where(Program.department_id == dept.id))
    p = res.scalar_one_or_none()
    assert p is not None
