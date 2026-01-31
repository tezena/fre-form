import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from app.main import app
from app.db.session import get_session
from app.models.department import Department
from app.models.user import UserRole


DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
async def engine():
    engine = create_async_engine(DATABASE_URL, echo=False, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def async_session(engine):
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with AsyncSessionLocal() as session:
        yield session


@pytest.fixture
async def client(async_session, monkeypatch):
    # override get_session to use the test session
    async def _get_session_override():
        async with sessionmaker(async_session.bind, class_=AsyncSession, expire_on_commit=False)() as s:
            yield s

    monkeypatch.setattr("app.api.v1.endpoints.students.get_session", _get_session_override)

    # stub auth to return a super admin user
    async def fake_current_active_user():
        class _U:
            id = 1
            role = UserRole.SUPER_ADMIN
            is_active = True
        return _U()

    app.dependency_overrides[get_session] = _get_session_override
    from app.core.dependencies import get_current_active_user

    app.dependency_overrides[get_current_active_user] = fake_current_active_user

    from httpx import ASGITransport
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.mark.anyio
async def test_create_and_get_student(client, async_session):
    # create a department first
    dept = Department(name="Test Dept")
    async_session.add(dept)
    await async_session.commit()
    await async_session.refresh(dept)

    payload = {
        "name": "Little Caleb",
        "age": 8,
        "sex": "M",
        "church": "St. Mary",
        "department_id": dept.id,
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

    r = await client.post("/api/v1/students/", json=payload)
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["name"] == "Little Caleb"
    student_id = data["id"]

    # get
    r2 = await client.get(f"/api/v1/students/{student_id}")
    assert r2.status_code == 200
    got = r2.json()
    assert got["category"] == "CHILDREN"
    assert got["category_details"]["child"]["parentName"] == "Sarah Connor"


@pytest.mark.anyio
async def test_list_update_delete_student(client, async_session):
    # create a department first
    dept = Department(name="Ops Dept")
    async_session.add(dept)
    await async_session.commit()
    await async_session.refresh(dept)

    # create student
    payload = {
        "name": "Abebe Bikila",
        "age": 35,
        "sex": "M",
        "church": "Medhane Alem",
        "department_id": dept.id,
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

    r = await client.post("/api/v1/students/", json=payload)
    assert r.status_code == 201
    student = r.json()

    # list
    rlist = await client.get("/api/v1/students/")
    assert rlist.status_code == 200
    items = rlist.json()
    assert any(s["id"] == student["id"] for s in items)

    # update - partial update nested
    update_payload = {
        "category_details": {
            "Adult": {
                "occupation": "Senior Engineer"
            }
        }
    }
    rupdate = await client.put(f"/api/v1/students/{student['id']}", json=update_payload)
    assert rupdate.status_code == 200
    updated = rupdate.json()
    assert updated["category_details"]["Adult"]["occupation"] == "Senior Engineer"

    # delete
    rdel = await client.delete(f"/api/v1/students/{student['id']}")
    assert rdel.status_code == 204

    # get should 404
    rget = await client.get(f"/api/v1/students/{student['id']}")
    assert rget.status_code == 404


@pytest.mark.anyio
async def test_invalid_missing_category_details(client, async_session):
    dept = Department(name="Invalid Dept")
    async_session.add(dept)
    await async_session.commit()
    await async_session.refresh(dept)

    payload = {
        "name": "No Details",
        "age": 10,
        "sex": "M",
        "church": "Test",
        "department_id": dept.id,
        "category": "CHILDREN",
        # missing category_details
    }
    r = await client.post("/api/v1/students/", json=payload)
    assert r.status_code == 422
