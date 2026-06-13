import pytest
from fastapi import HTTPException
from backend.api.auth.security import get_password_hash, verify_password, create_access_token, decode_access_token

def test_password_hashing():
    password = "secretpassword"
    hashed = get_password_hash(password)
    assert password != hashed
    assert verify_password(password, hashed) is True
    assert verify_password("wrongpassword", hashed) is False

def test_token_generation_not_implemented():
    with pytest.raises(HTTPException) as exc:
        create_access_token({"sub": "user"})
    assert exc.value.status_code == 501

def test_token_decoding_not_implemented():
    with pytest.raises(HTTPException) as exc:
        decode_access_token("some.token.string")
    assert exc.value.status_code == 501
