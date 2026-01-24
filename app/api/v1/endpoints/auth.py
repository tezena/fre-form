from datetime import timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm  # <--- IMPORT THIS
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_session
from app.models.user import User
from app.core.security import verify_password, create_access_token
from app.core.config import settings
from app.schemas.user import Token # Removed UserLogin, we don't need it here anymore

router = APIRouter()

@router.post("/login", response_model=Token)
async def login(
    # CHANGE 1: Use the OAuth2 Form dependency instead of UserLogin schema
    form_data: OAuth2PasswordRequestForm = Depends(), 
    session: AsyncSession = Depends(get_session),
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests.
    """
    # CHANGE 2: The form always calls the field 'username', even if we use Email
    result = await session.execute(
        select(User).where(User.email == form_data.username) 
    )
    user = result.scalar_one_or_none()

    # CHANGE 3: Use form_data.password
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # CHANGE 4: Ensure user.id is a string to prevent JSON errors
    access_token = create_access_token(
        data={"sub": user.email, "user_id": str(user.id)}, 
        expires_delta=access_token_expires,
    )

    return {
        "access_token": access_token, 
        "token_type": "bearer"
    }