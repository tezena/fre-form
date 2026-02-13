from typing import Optional, Annotated, List, Tuple
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlmodel import select as sqlmodel_select

from app.db.session import get_session
from app.models.user import User, UserRole, UserDepartment
# 1. CHANGE: Import 'decode_token' instead of 'decode_access_token'
from app.core.security import decode_token

# Define the OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    """
    Validate the access token and return the current user.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 2. CHANGE: Use the new decoder
    payload = decode_token(token)
    if payload is None:
        raise credentials_exception

    # 3. CHANGE: Verify this is an 'access' token (not a refresh token)
    token_type = payload.get("type")
    if token_type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type (access token required)",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 4. CHANGE: Extract User ID (sub), not Email
    user_id_str: str = payload.get("sub")
    if user_id_str is None:
        raise credentials_exception
    
    try:
        user_id = int(user_id_str)
    except ValueError:
        raise credentials_exception

    # 5. CHANGE: Query by ID instead of Email
    result = await session.execute(
        select(User).where(User.id == user_id)
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
) -> Tuple[User, AsyncSession]:
    """
    Get current user with session for permission checks.
    """
    return current_user, session


async def require_admin_department_access(
    department_id: int,
    current_user_and_session: Tuple[User, AsyncSession] = Depends(
        get_current_active_user_with_permissions
    ),
) -> Tuple[User, AsyncSession]:
    """
    Dependency that ensures an Admin has access to the specified department.
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
    current_user_and_session: Tuple[User, AsyncSession] = Depends(
        get_current_active_user_with_permissions
    ),
) -> Tuple[User, AsyncSession]:
    """
    Dependency that ensures a Manager has access to the specified department.
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