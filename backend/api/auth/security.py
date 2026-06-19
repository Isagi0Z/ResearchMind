import hashlib
import jwt
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from typing import Optional, Dict, Any
from backend.api.config import settings

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7
JWT_ISSUER = "researchmind-api"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def sha256_digest(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def _build_payload(data: dict, expires_at: datetime, token_type: str) -> dict:
    payload = data.copy()
    payload.update({
        "exp": expires_at,
        "iss": JWT_ISSUER,
        "type": token_type,
    })
    return payload


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = _build_payload(to_encode, expire, "access")
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = _build_payload(to_encode, expire, "refresh")
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str, expected_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        if expected_type and payload.get("type") != expected_type:
            return None
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.PyJWTError:
        return None


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    return decode_token(token, expected_type="access")
