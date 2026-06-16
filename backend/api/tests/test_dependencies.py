import pytest
from fastapi import HTTPException
from backend.api.auth.security import create_access_token, decode_access_token

def test_get_current_user_token_flow():
    payload = {"sub": "user-id-123", "role": "user"}
    token = create_access_token(payload)
    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == "user-id-123"
    assert decoded["role"] == "user"

def test_decode_expired_or_invalid_token():
    assert decode_access_token("bogus.token.value") is None
