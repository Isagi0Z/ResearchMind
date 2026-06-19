from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
from typing import Optional
import uuid

from backend.db.session import get_db
from backend.db.models.user import User
from backend.db.models.refresh_token import RefreshToken
from backend.api.auth.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token,
    decode_access_token,
    sha256_digest,
)
from backend.api.auth.cookies import set_auth_cookies, clear_auth_cookies, ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE
from backend.api.dependencies import get_current_user
from backend.api.config import settings

router = APIRouter()

class UserCreate(BaseModel):
    username: str
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class UserProfile(BaseModel):
    id: str
    username: str
    email: str
    role: str
    is_active: bool
    created_at: str

class RefreshRequest(BaseModel):
    refresh_token: Optional[str] = None

@router.post("/register", response_model=dict)
async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where((User.username == user_in.username) | (User.email == user_in.email))
    )
    if result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered"
        )
    
    new_user = User(
        username=user_in.username,
        email=user_in.email,
        password_hash=get_password_hash(user_in.password)
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return {"message": "User registered successfully"}

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), response: Response = None, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": str(user.id), "role": user.role})
    raw_refresh_token = create_refresh_token(data={"sub": str(user.id)})

    # Store hashed refresh token
    hashed_refresh = get_password_hash(raw_refresh_token)
    payload = decode_token(raw_refresh_token)
    expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)

    db_token = RefreshToken(
        user_id=user.id,
        hashed_token=hashed_refresh,
        token_hash_sha256=sha256_digest(raw_refresh_token),
        expires_at=expires_at
    )
    db.add(db_token)
    await db.commit()

    set_auth_cookies(response, access_token, raw_refresh_token)
    return {"access_token": access_token, "refresh_token": raw_refresh_token, "token_type": "bearer"}

@router.post("/refresh", response_model=Token)
async def refresh_token(request: RefreshRequest, http_request: Request = None, response: Response = None, db: AsyncSession = Depends(get_db)):
    # Support cookie-based refresh token as fallback
    raw_token = request.refresh_token
    if not raw_token:
        raw_token = http_request.cookies.get(REFRESH_TOKEN_COOKIE)
    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token missing")
    payload = decode_token(raw_token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
        
    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user ID")

    # Look up the token by SHA256 hash for O(1) fast lookup
    token_hash = sha256_digest(raw_token)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash_sha256 == token_hash,
            RefreshToken.is_revoked == False,
            RefreshToken.expires_at > datetime.now(timezone.utc)
        )
    )
    matched_token = result.scalar_one_or_none()

    if not matched_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked refresh token")

    # Rotate token
    matched_token.is_revoked = True

    user_res = await db.execute(select(User).where(User.id == user_id))
    user = user_res.scalar_one_or_none()
    if not user or not user.is_active:
         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive or deleted")

    new_access_token = create_access_token(data={"sub": str(user.id), "role": user.role})
    new_raw_refresh = create_refresh_token(data={"sub": str(user.id)})

    new_hashed_refresh = get_password_hash(new_raw_refresh)
    new_payload = decode_token(new_raw_refresh)
    new_expires_at = datetime.fromtimestamp(new_payload["exp"], tz=timezone.utc)

    new_db_token = RefreshToken(
        user_id=user.id,
        hashed_token=new_hashed_refresh,
        token_hash_sha256=sha256_digest(new_raw_refresh),
        expires_at=new_expires_at
    )
    db.add(new_db_token)
    await db.commit()

    set_auth_cookies(response, new_access_token, new_raw_refresh)
    return {"access_token": new_access_token, "refresh_token": new_raw_refresh, "token_type": "bearer"}

@router.get("/me", response_model=UserProfile)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserProfile(
        id=str(current_user.id),
        username=current_user.username,
        email=current_user.email,
        role=current_user.role,
        is_active=current_user.is_active,
        created_at=str(current_user.created_at)
    )

@router.post("/logout")
async def logout(request: RefreshRequest, http_request: Request = None, response: Response = None, db: AsyncSession = Depends(get_db)):
    raw_token = request.refresh_token
    if not raw_token:
        raw_token = http_request.cookies.get(REFRESH_TOKEN_COOKIE)
    if not raw_token:
        clear_auth_cookies(response)
        return {"message": "Logged out"}

    payload = decode_token(raw_token)
    if not payload:
        clear_auth_cookies(response)
        return {"message": "Logged out"}

    user_id_str = payload.get("sub")
    if not user_id_str:
        clear_auth_cookies(response)
        return {"message": "Logged out"}

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        clear_auth_cookies(response)
        return {"message": "Logged out"}

    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash_sha256 == sha256_digest(raw_token),
            RefreshToken.is_revoked == False
        )
    )
    matched_token = result.scalar_one_or_none()

    if matched_token:
        matched_token.is_revoked = True

    await db.commit()
    clear_auth_cookies(response)
    return {"message": "Logged out successfully"}
