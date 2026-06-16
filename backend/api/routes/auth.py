from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
import uuid

from backend.db.session import get_db
from backend.db.models.user import User
from backend.db.models.refresh_token import RefreshToken
from backend.api.auth.security import (
    verify_password, 
    get_password_hash, 
    create_access_token, 
    create_refresh_token,
    decode_token
)
from backend.api.dependencies import get_current_user

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
    refresh_token: str

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
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
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
        expires_at=expires_at
    )
    db.add(db_token)
    await db.commit()
    
    return {"access_token": access_token, "refresh_token": raw_refresh_token, "token_type": "bearer"}

@router.post("/refresh", response_model=Token)
async def refresh_token(request: RefreshRequest, db: AsyncSession = Depends(get_db)):
    payload = decode_token(request.refresh_token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
        
    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user ID")

    # Find the refresh token in the DB that matches the hashed token
    # Since we hashed it with bcrypt, we have to fetch all valid tokens for the user and verify
    # This is slightly inefficient but safe. We can also store the raw token's hash with SHA256 instead for fast lookup.
    # To keep it simple and safe based on "Store hashed refresh token" requirement:
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.is_revoked == False,
            RefreshToken.expires_at > datetime.now(timezone.utc)
        )
    )
    tokens = result.scalars().all()
    
    matched_token = None
    for t in tokens:
        if verify_password(request.refresh_token, t.hashed_token):
            matched_token = t
            break
            
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
        expires_at=new_expires_at
    )
    db.add(new_db_token)
    await db.commit()
    
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
async def logout(request: RefreshRequest, db: AsyncSession = Depends(get_db)):
    payload = decode_token(request.refresh_token)
    if not payload:
        return {"message": "Logged out"}
        
    user_id_str = payload.get("sub")
    if not user_id_str:
        return {"message": "Logged out"}
        
    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        return {"message": "Logged out"}
        
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.is_revoked == False
        )
    )
    tokens = result.scalars().all()
    
    for t in tokens:
        if verify_password(request.refresh_token, t.hashed_token):
            t.is_revoked = True
            break
            
    await db.commit()
    return {"message": "Logged out successfully"}
