import pytest
from app.core.dependencies import get_current_active_user
from app.models.user import UserRole


@pytest.mark.anyio
async def test_department_crud_and_permissions(client):
    # create department as super admin (fixture)
    payload = {"name": "QA Dept", "description": "Quality Assurance"}
    r = await client.post("/api/v1/departments/", json=payload)
    assert r.status_code == 201
    dept = r.json()

    # duplicate name should fail
    rdup = await client.post("/api/v1/departments/", json=payload)
    assert rdup.status_code == 400

    # get department
    rget = await client.get(f"/api/v1/departments/{dept['id']}")
    assert rget.status_code == 200

    # update department
    rupdate = await client.put(f"/api/v1/departments/{dept['id']}", json={"description": "QA Team"})
    assert rupdate.status_code == 200
    assert rupdate.json()["description"] == "QA Team"

    # try create department as non-super-admin -> should be forbidden
    async def fake_user():
        class _U:
            id = 99
            role = UserRole.ADMIN
            is_active = True
        return _U()

    orig = client.app.dependency_overrides.get(get_current_active_user)
    client.app.dependency_overrides[get_current_active_user] = fake_user
    r403 = await client.post("/api/v1/departments/", json={"name": "X"})
    assert r403.status_code == 403
    # restore
    if orig is not None:
        client.app.dependency_overrides[get_current_active_user] = orig
    else:
        client.app.dependency_overrides.pop(get_current_active_user, None)

    # delete department as super admin
    rdel = await client.delete(f"/api/v1/departments/{dept['id']}")
    assert rdel.status_code == 204


@pytest.mark.anyio
async def test_user_creation_and_manager_workflow(client):
    # create a department
    rp = await client.post("/api/v1/departments/", json={"name": "HR Dept"})
    assert rp.status_code == 201
    dept = rp.json()

    # create a normal user with department_ids
    user_payload = {
        "email": "user1@example.com",
        "full_name": "User One",
        "role": "ADULT",  # role value is ignored by create_user when creating admins/managers
        "password": "secret",
        "department_ids": [dept['id']]
    }
    ruser = await client.post("/api/v1/users/", json=user_payload)
    assert ruser.status_code == 201

    # create an Admin via super-admin endpoint
    admin_payload = {
        "email": "admin1@example.com",
        "full_name": "Admin One",
        "role": "ADMIN",
        "password": "secret",
    }
    radmin = await client.post(f"/api/v1/users/super-admin/create-admin?department_id={dept['id']}", json=admin_payload)
    assert radmin.status_code == 201
    admin = radmin.json()

    # as super admin, create a Manager for the department
    mgr_payload = {"email": "mgr1@example.com", "full_name": "Manager One", "role": "MANAGER", "password": "secret"}
    rmgr = await client.post(f"/api/v1/users/admin/create-manager?department_id={dept['id']}", json=mgr_payload)
    assert rmgr.status_code == 201

    # Now simulate Admin user by overriding dependency
    async def fake_admin():
        class _U:
            id = admin['id']
            role = UserRole.ADMIN
            is_active = True
        return _U()

    orig = client.app.dependency_overrides.get(get_current_active_user)
    client.app.dependency_overrides[get_current_active_user] = fake_admin

    # Admin should be able to create a manager in their department
    mgr2_payload = {"email": "mgr2@example.com", "full_name": "Manager Two", "role": "MANAGER", "password": "secret"}
    rmgr2 = await client.post(f"/api/v1/users/admin/create-manager?department_id={dept['id']}", json=mgr2_payload)
    assert rmgr2.status_code == 201

    # restore override
    if orig is not None:
        client.app.dependency_overrides[get_current_active_user] = orig
    else:
        client.app.dependency_overrides.pop(get_current_active_user, None)


@pytest.mark.anyio
async def test_user_create_invalid_department(client):
    payload = {"email": "bad@example.com", "full_name": "Bad", "role": "ADMIN", "password": "x", "department_ids": [9999]}
    r = await client.post("/api/v1/users/", json=payload)
    assert r.status_code == 404
