from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlmodel import select as sqlmodel_select
from app.db.session import get_session
from app.models.user import User, UserRole, UserDepartment
from app.models.department import Department
from app.core.dependencies import (
    get_current_active_user,
    get_current_super_admin,
    get_current_admin,
    require_admin_department_access,
    get_user_departments,
)
from app.core.security import get_password_hash
from app.schemas.user import UserCreate, UserUpdate, UserResponse

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """Get current user information."""
    department_ids = await get_user_departments(current_user.id, session)
    user_dict = current_user.model_dump()
    user_dict["department_ids"] = department_ids
    return UserResponse(**user_dict)


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(get_current_super_admin),
    session: AsyncSession = Depends(get_session),
):
    """Create a new user. Only Super Admin can create users."""
    # Check if email already exists
    result = await session.execute(
        select(User).where(User.email == user_data.email)
    )
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Validate role assignment rules
    if user_data.role == UserRole.SUPER_ADMIN:
        # Only existing Super Admin can create another Super Admin
        if current_user.role != UserRole.SUPER_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Super Admin can create another Super Admin"
            )

    # Create user
    new_user = User(
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        role=user_data.role,
        is_active=True,
    )
    session.add(new_user)
    await session.flush()

    # Assign departments if provided
    if user_data.department_ids:
        # Validate departments exist
        result = await session.execute(
            select(Department).where(Department.id.in_(user_data.department_ids))
        )
        departments = result.scalars().all()
        if len(departments) != len(user_data.department_ids):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or more departments not found"
            )

        # Add department associations
        for dept_id in user_data.department_ids:
            user_dept = UserDepartment(user_id=new_user.id, department_id=dept_id)
            session.add(user_dept)

    await session.commit()
    await session.refresh(new_user)

    department_ids = await get_user_departments(new_user.id, session)
    user_dict = new_user.model_dump()
    user_dict["department_ids"] = department_ids
    return UserResponse(**user_dict)


@router.post("/admin/create-manager", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_manager(
    user_data: UserCreate,
    department_id: int,
    current_user_and_session: tuple[User, AsyncSession] = Depends(
        require_admin_department_access
    ),
):
    """
    Create a Manager user. Admin can only create Managers in their assigned departments.
    Super Admin can create Managers in any department.
    """
    current_user, session = current_user_and_session

    # Ensure we're creating a Manager
    if user_data.role != UserRole.MANAGER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This endpoint can only create Manager users"
        )

    # Check if email already exists
    result = await session.execute(
        select(User).where(User.email == user_data.email)
    )
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Validate department exists
    result = await session.execute(
        select(Department).where(Department.id == department_id)
    )
    department = result.scalar_one_or_none()
    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )

    # Create Manager user
    new_user = User(
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        role=UserRole.MANAGER,
        is_active=True,
    )
    session.add(new_user)
    await session.flush()

    # Assign to the specified department
    user_dept = UserDepartment(user_id=new_user.id, department_id=department_id)
    session.add(user_dept)

    await session.commit()
    await session.refresh(new_user)

    department_ids = await get_user_departments(new_user.id, session)
    user_dict = new_user.model_dump()
    user_dict["department_ids"] = department_ids
    return UserResponse(**user_dict)


@router.post(
    "/super-admin/create-admin",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_admin(
    user_data: UserCreate,
    department_id: int,
    current_user: User = Depends(get_current_super_admin),
    session: AsyncSession = Depends(get_session),
):
    """
    Create an Admin user and assign them to exactly one department.
    Only Super Admin can call this.
    """
    # Check if email already exists
    result = await session.execute(
        select(User).where(User.email == user_data.email)
    )
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Validate department exists
    result = await session.execute(
        select(Department).where(Department.id == department_id)
    )
    department = result.scalar_one_or_none()
    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found",
        )

    # Create Admin user (force role to ADMIN regardless of payload)
    new_user = User(
        email=user_data.email,
        password_hash=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        role=UserRole.ADMIN,
        is_active=True,
    )
    session.add(new_user)
    await session.flush()

    # Assign exactly one department
    user_dept = UserDepartment(user_id=new_user.id, department_id=department_id)
    session.add(user_dept)

    await session.commit()
    await session.refresh(new_user)

    department_ids = await get_user_departments(new_user.id, session)
    user_dict = new_user.model_dump()
    user_dict["department_ids"] = department_ids
    return UserResponse(**user_dict)


@router.get("/", response_model=List[UserResponse])
async def list_users(
    current_user: User = Depends(get_current_super_admin),
    session: AsyncSession = Depends(get_session),
):
    """List all users. Only Super Admin can list all users."""
    result = await session.execute(select(User))
    users = result.scalars().all()

    user_responses = []
    for user in users:
        department_ids = await get_user_departments(user.id, session)
        user_dict = user.model_dump()
        user_dict["department_ids"] = department_ids
        user_responses.append(UserResponse(**user_dict))

    return user_responses


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    current_user: User = Depends(get_current_super_admin),
    session: AsyncSession = Depends(get_session),
):
    """Get a specific user. Only Super Admin can view any user."""
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    department_ids = await get_user_departments(user.id, session)
    user_dict = user.model_dump()
    user_dict["department_ids"] = department_ids
    return UserResponse(**user_dict)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_user: User = Depends(get_current_super_admin),
    session: AsyncSession = Depends(get_session),
):
    """Update a user. Only Super Admin can update users."""
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Update fields
    update_data = user_update.model_dump(exclude_unset=True, exclude={"department_ids"})
    for field, value in update_data.items():
        setattr(user, field, value)

    # Update departments if provided
    if user_update.department_ids is not None:
        # Remove existing associations
        await session.execute(
            sqlmodel_select(UserDepartment).where(UserDepartment.user_id == user_id)
        )
        result = await session.execute(
            sqlmodel_select(UserDepartment).where(UserDepartment.user_id == user_id)
        )
        existing_assocs = result.scalars().all()
        for assoc in existing_assocs:
            await session.delete(assoc)

        # Add new associations
        if user_update.department_ids:
            result = await session.execute(
                select(Department).where(Department.id.in_(user_update.department_ids))
            )
            departments = result.scalars().all()
            if len(departments) != len(user_update.department_ids):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="One or more departments not found"
                )

            for dept_id in user_update.department_ids:
                user_dept = UserDepartment(user_id=user_id, department_id=dept_id)
                session.add(user_dept)

    await session.commit()
    await session.refresh(user)

    department_ids = await get_user_departments(user.id, session)
    user_dict = user.model_dump()
    user_dict["department_ids"] = department_ids
    return UserResponse(**user_dict)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_super_admin),
    session: AsyncSession = Depends(get_session),
):
    """Delete a user. Only Super Admin can delete users."""
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    await session.delete(user)
    await session.commit()
    return None


@router.delete(
    "/super-admin/admins/{admin_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_admin(
    admin_id: int,
    current_user: User = Depends(get_current_super_admin),
    session: AsyncSession = Depends(get_session),
):
    """
    Delete an Admin user by id.
    Only Super Admin can call this.
    """
    result = await session.execute(select(User).where(User.id == admin_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Target user is not an Admin",
        )

    await session.delete(user)
    await session.commit()
    return None

