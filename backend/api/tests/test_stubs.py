import pytest

IMPLEMENTED_ROUTES = [
    ("GET", "/api/v1/graph", None),
    ("GET", "/api/v1/graph/data", None),
    ("GET", "/api/v1/documents", None),
    ("GET", "/api/v1/dashboard/summary", None),
    ("GET", "/api/v1/dashboard/status", None),
    ("GET", "/api/v1/dashboard/recent", None),
    ("GET", "/api/v1/monitoring", None),
]

def test_auth_login_no_user(client):
    """No registered user — expect 401."""
    response = client.post("/api/v1/auth/login", headers={"Content-Type": "application/x-www-form-urlencoded"}, data={"username": "nonexistent", "password": "pwd"})
    assert response.status_code == 401

def test_auth_register_creates_user(client):
    """Register returns 200 and creates user."""
    response = client.post("/api/v1/auth/register", json={"username": "testuser", "password": "pwd123", "email": "test@example.com"})
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "User registered successfully"

def test_auth_register_duplicate(client):
    """Registering same user twice returns 400."""
    client.post("/api/v1/auth/register", json={"username": "dupuser", "password": "pwd", "email": "dup@example.com"})
    response = client.post("/api/v1/auth/register", json={"username": "dupuser", "password": "pwd", "email": "dup@example.com"})
    assert response.status_code == 400

def test_auth_login_after_register(client):
    """After registration, login returns tokens."""
    client.post("/api/v1/auth/register", json={"username": "logintest", "password": "secret", "email": "login@test.com"})
    response = client.post("/api/v1/auth/login", headers={"Content-Type": "application/x-www-form-urlencoded"}, data={"username": "logintest", "password": "secret"})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"

def test_auth_refresh_after_login(client):
    """Refresh endpoint returns new tokens with a valid refresh token."""
    client.post("/api/v1/auth/register", json={"username": "refreshtest", "password": "secret", "email": "refresh@test.com"})
    login_resp = client.post("/api/v1/auth/login", headers={"Content-Type": "application/x-www-form-urlencoded"}, data={"username": "refreshtest", "password": "secret"})
    refresh_token = login_resp.json()["refresh_token"]
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data

def test_auth_refresh_invalid(client):
    """Invalid refresh token returns 401."""
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": "bogus.token.here"})
    assert response.status_code == 401

def test_auth_logout(client):
    """Logout with valid refresh token succeeds."""
    client.post("/api/v1/auth/register", json={"username": "logouttest", "password": "secret", "email": "logout@test.com"})
    login_resp = client.post("/api/v1/auth/login", headers={"Content-Type": "application/x-www-form-urlencoded"}, data={"username": "logouttest", "password": "secret"})
    refresh_token = login_resp.json()["refresh_token"]
    response = client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
    assert response.status_code == 200
    assert response.json()["message"] == "Logged out successfully"

def test_auth_me_no_token(client):
    """GET /me without token returns 401."""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401

def test_auth_me_with_token(client):
    """GET /me with valid token returns user profile."""
    client.post("/api/v1/auth/register", json={"username": "meprofile", "password": "secret", "email": "me@test.com"})
    login_resp = client.post("/api/v1/auth/login", headers={"Content-Type": "application/x-www-form-urlencoded"}, data={"username": "meprofile", "password": "secret"})
    access_token = login_resp.json()["access_token"]
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "meprofile"
    assert data["email"] == "me@test.com"
    assert "role" in data

@pytest.mark.parametrize("method, path, body", IMPLEMENTED_ROUTES)
def test_implemented_routes(client, method, path, body):
    response = client.get(path)
    assert response.status_code == 200

@pytest.mark.parametrize("iteration", range(15))
@pytest.mark.parametrize("method, path, body", [
    ("GET", "/api/v1/graph", None),
    ("GET", "/api/v1/dashboard/summary", None)
])
def test_implemented_fuzz(client, method, path, body, iteration):
    response = client.get(path)
    assert response.status_code == 200
