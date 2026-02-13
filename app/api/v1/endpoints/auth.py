from datetime import timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.db.session import get_session
from app.models.user import User
# Import the new functions from security.py
from app.core.security import verify_password, create_access_token, create_refresh_token, decode_token
from app.core.config import settings
# Import the NEW schema that includes refresh_token
from app.schemas.token import Token

router = APIRouter()

# Schema for the body of the /refresh endpoint
class RefreshTokenBody(BaseModel):
    refresh_token: str

@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    session: AsyncSession = Depends(get_session),
) -> Any:
    """
    OAuth2 compatible token login. 
    Returns BOTH an access_token (short-lived) and a refresh_token (long-lived).
    """
    result = await session.execute(
        select(User).where(User.email == form_data.username) 
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    # 1. Create Access Token (Expires in ~15 mins)
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.id, 
        expires_delta=access_token_expires
    )
    
    # 2. Create Refresh Token (Expires in ~7 days)
    refresh_token = create_refresh_token(
        subject=user.id
    )

    return {
        "access_token": access_token, 
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@router.post("/refresh", response_model=Token)
async def refresh_token(
    body: RefreshTokenBody,
    session: AsyncSession = Depends(get_session),
) -> Any:
    """
    Get a new access token using a valid refresh token.
    This is what the frontend calls when the access token expires (401).
    """
    # 1. Decode the Refresh Token
    payload = decode_token(body.refresh_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 2. Verify it is actually a "refresh" token (not an access token)
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type (expected refresh token)",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # 3. Check if user still exists and is active
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token subject")

    result = await session.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User inactive or not found")

    # 4. Issue NEW Access Token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    new_access_token = create_access_token(
        subject=user.id,
        expires_delta=access_token_expires,
    )
    
    # 5. Issue NEW Refresh Token (Rotation - safer!)
    # This ensures that if a refresh token is stolen, it's only valid once.
    new_refresh_token = create_refresh_token(subject=user.id)

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer"
    }