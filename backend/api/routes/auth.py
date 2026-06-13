from fastapi import APIRouter, HTTPException
from backend.api.schemas.auth import UserLogin, UserRegister, Token

router = APIRouter()

@router.post("/login", response_model=Token)
async def login(credentials: UserLogin):
    raise HTTPException(status_code=501, detail="Not Implemented")

@router.post("/register")
async def register(user: UserRegister):
    raise HTTPException(status_code=501, detail="Not Implemented")

@router.post("/refresh")
async def refresh_token():
    raise HTTPException(status_code=501, detail="Not Implemented")

@router.post("/logout")
async def logout():
    raise HTTPException(status_code=501, detail="Not Implemented")
