from passlib.context import CryptContext
from fastapi import HTTPException
from typing import Optional

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[int] = None) -> str:
    raise HTTPException(status_code=501, detail="Not Implemented")

def decode_access_token(token: str) -> Optional[dict]:
    raise HTTPException(status_code=501, detail="Not Implemented")
