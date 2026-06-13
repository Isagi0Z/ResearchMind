import pytest
from backend.api.exceptions import ResearchMindException, AuthException, create_error_envelope

def test_base_exception():
    exc = ResearchMindException(code="ERR1", message="Test message", status_code=400)
    assert exc.code == "ERR1"
    assert exc.message == "Test message"
    assert exc.status_code == 400

def test_auth_exception():
    exc = AuthException()
    assert exc.code == "AUTH_ERROR"
    assert exc.status_code == 401
    assert exc.message == "Authentication failed"
    
    exc2 = AuthException(message="Custom")
    assert exc2.message == "Custom"

def test_create_error_envelope():
    env = create_error_envelope("CODE", "Message", "req-123")
    assert "error" in env
    assert env["error"]["code"] == "CODE"
    assert env["error"]["message"] == "Message"
    assert env["error"]["request_id"] == "req-123"

def test_404_not_found(client):
    response = client.get("/api/v1/doesnotexist")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "HTTP_ERROR"
    assert "request_id" in data["error"]

def test_405_method_not_allowed(client):
    response = client.post("/api/v1/health")
    assert response.status_code == 405
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "HTTP_ERROR"

def test_validation_error(client):
    # Send a request missing a required body to trigger 422
    response = client.post("/api/v1/auth/login", json={})
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert data["error"]["message"] == "Request validation failed"
    assert "request_id" in data["error"]

@pytest.mark.parametrize("i", range(10))
def test_validation_error_multiple(client, i):
    response = client.post("/api/v1/auth/login", json={"missing": "stuff", "i": i})
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"
