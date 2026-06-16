from backend.api.auth.security import get_password_hash, verify_password, create_access_token, decode_access_token

def test_password_hashing():
    password = "secretpassword"
    hashed = get_password_hash(password)
    assert password != hashed
    assert verify_password(password, hashed) is True
    assert verify_password("wrongpassword", hashed) is False

def test_token_generation_and_decoding():
    payload = {"sub": "user-id-123", "role": "user"}
    token = create_access_token(payload)
    assert isinstance(token, str)
    assert len(token) > 20

    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == "user-id-123"
    assert decoded["role"] == "user"

def test_decode_invalid_token():
    assert decode_access_token("invalid.token.here") is None
    assert decode_access_token("") is None
