from typing import Optional, Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlmodel import select as sqlmodel_select
from app.db.session import get_session
from app.models.user import User, UserRole, UserDepartment
from app.core.security import decode_access_token
from app.schemas.user import TokenData

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Get the current authenticated user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    email: str = payload.get("sub")
    if email is None:
        raise credentials_exception

    token_data = TokenData(email=email)

    # Fetch user from database
    result = await session.execute(
        select(User).where(User.email == token_data.email)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get the current active user."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user


async def get_current_super_admin(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Ensure the current user is a Super Admin."""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. Super Admin access required."
        )
    return current_user


async def get_current_admin(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Ensure the current user is an Admin or Super Admin."""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. Admin access required."
        )
    return current_user


async def get_user_departments(
    user_id: int,
    session: AsyncSession,
) -> list[int]:
    """Get list of department IDs for a user."""
    result = await session.execute(
        sqlmodel_select(UserDepartment).where(UserDepartment.user_id == user_id)
    )
    user_departments = result.scalars().all()
    return [ud.department_id for ud in user_departments]


async def check_admin_department_access(
    user: User,
    department_id: int,
    session: AsyncSession,
) -> bool:
    """Check if a user (Admin or Manager) has access to a specific department."""
    if user.role == UserRole.SUPER_ADMIN:
        return True

    if user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
        return False

    user_departments = await get_user_departments(user.id, session)
    return department_id in user_departments


async def get_current_active_user_with_permissions(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
) -> tuple[User, AsyncSession]:
    """
    Get current user with session for permission checks.
    Used for operations that require department-based scoping.
    """
    return current_user, session


async def require_admin_department_access(
    department_id: int,
    current_user_and_session: tuple[User, AsyncSession] = Depends(
        get_current_active_user_with_permissions
    ),
) -> tuple[User, AsyncSession]:
    """
    Dependency that ensures an Admin has access to the specified department.
    Super Admins have access to all departments.
    """
    current_user, session = current_user_and_session

    if current_user.role == UserRole.SUPER_ADMIN:
        return current_user, session

    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. Admin access required."
        )

    has_access = await check_admin_department_access(
        current_user, department_id, session
    )

    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Admin does not have access to department {department_id}"
        )

    return current_user, session


async def require_manager_department_access(
    department_id: int,
    current_user_and_session: tuple[User, AsyncSession] = Depends(
        get_current_active_user_with_permissions
    ),
) -> tuple[User, AsyncSession]:
    """
    Dependency that ensures a Manager has access to the specified department.
    Super Admins and Admins have access to all departments.
    """
    current_user, session = current_user_and_session

    if current_user.role in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        return current_user, session

    if current_user.role != UserRole.MANAGER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. Manager access required."
        )

    has_access = await check_admin_department_access(
        current_user, department_id, session
    )

    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Manager does not have access to department {department_id}"
        )

    return current_user, session

