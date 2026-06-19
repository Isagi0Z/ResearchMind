import pytest
import asyncio
from sqlalchemy import text

IMPLEMENTED_ROUTES = [
    ("GET", "/api/v1/graph", None),
    ("GET", "/api/v1/graph/data", None),
    ("GET", "/api/v1/documents", None),
    ("GET", "/api/v1/dashboard/summary", None),
    ("GET", "/api/v1/dashboard/status", None),
    ("GET", "/api/v1/dashboard/recent", None),
]

def _register_and_login(client, username="testuser", password="secret", email="test@example.com"):
    client.post("/api/v1/auth/register", json={"username": username, "password": password, "email": email})
    resp = client.post("/api/v1/auth/login", headers={"Content-Type": "application/x-www-form-urlencoded"}, data={"username": username, "password": password})
    assert resp.status_code == 200, f"Login failed for {username}: {resp.text}"
    return resp.json()

def _make_admin(username):
    from backend.db.session import engine
    async def _set_role():
        async with engine.begin() as conn:
            await conn.execute(text("UPDATE users SET role = 'admin' WHERE username = :username"), {"username": username})
    asyncio.get_event_loop().run_until_complete(_set_role())

# --- Auth Tests ---

def test_auth_login_no_user(client):
    response = client.post("/api/v1/auth/login", headers={"Content-Type": "application/x-www-form-urlencoded"}, data={"username": "nonexistent", "password": "pwd"})
    assert response.status_code == 401

def test_auth_register_creates_user(client):
    response = client.post("/api/v1/auth/register", json={"username": "testuser", "password": "pwd123", "email": "test@example.com"})
    assert response.status_code == 200
    assert response.json()["message"] == "User registered successfully"

def test_auth_register_duplicate(client):
    client.post("/api/v1/auth/register", json={"username": "dupuser", "password": "pwd", "email": "dup@example.com"})
    response = client.post("/api/v1/auth/register", json={"username": "dupuser", "password": "pwd", "email": "dup@example.com"})
    assert response.status_code == 400

def test_auth_login_after_register(client):
    _register_and_login(client, "logintest", "secret", "login@test.com")
    # Already tested via helper — check we get tokens
    data = _register_and_login(client, "logintest2", "secret", "login2@test.com")
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"

def test_auth_refresh_after_login(client):
    tokens = _register_and_login(client, "refreshtest", "secret", "refresh@test.com")
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data

def test_auth_refresh_invalid(client):
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": "bogus.token.here"})
    assert response.status_code == 401

def test_auth_logout(client):
    tokens = _register_and_login(client, "logouttest", "secret", "logout@test.com")
    response = client.post("/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]})
    assert response.status_code == 200
    assert response.json()["message"] == "Logged out successfully"

def test_auth_me_no_token(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401

def test_auth_me_with_token(client):
    tokens = _register_and_login(client, "meprofile", "secret", "me@test.com")
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "meprofile"
    assert data["email"] == "me@test.com"
    assert "role" in data

# --- Route Stub Tests ---

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

# --- W4: RBAC Tests ---

def test_monitoring_requires_admin(client):
    response = client.get("/api/v1/monitoring")
    assert response.status_code == 401

def test_monitoring_admin_allowed(client):
    tokens = _register_and_login(client, "adminuser", "admin123", "admin@test.com")
    _make_admin("adminuser")
    response = client.get("/api/v1/monitoring", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert "health" in data

def test_monitoring_metrics_admin_allowed(client):
    tokens = _register_and_login(client, "adminuser2", "admin123", "admin2@test.com")
    _make_admin("adminuser2")
    response = client.get("/api/v1/monitoring/metrics", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert response.status_code == 200

# --- W5: Monitoring Filter Tests ---

def test_monitoring_time_range_accepted(client):
    tokens = _register_and_login(client, "adminmt1", "admin123", "mt1@test.com")
    _make_admin("adminmt1")
    response = client.get("/api/v1/monitoring?timeRange=1h", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert response.status_code == 200

def test_monitoring_time_range_default(client):
    tokens = _register_and_login(client, "adminmt2", "admin123", "mt2@test.com")
    _make_admin("adminmt2")
    response = client.get("/api/v1/monitoring", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert response.status_code == 200

# --- W6: Graph Node Detail Tests ---

def test_graph_node_detail_found(client):
    response = client.get("/api/v1/graph/node/doc-0")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "doc-0"

def test_graph_node_detail_not_found(client):
    response = client.get("/api/v1/graph/node/nonexistent")
    assert response.status_code == 404

# --- W2: Documents Search Tests ---

def test_documents_default_pagination(client):
    response = client.get("/api/v1/documents")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "total" in data
    assert len(data["data"]) <= 10

def test_documents_search_query(client):
    response = client.get("/api/v1/documents?searchQuery=Research")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) >= 0

def test_documents_sort_by_title(client):
    response = client.get("/api/v1/documents?sortBy=title&sortDirection=asc")
    assert response.status_code == 200

def test_documents_pagination_offset(client):
    r1 = client.get("/api/v1/documents?pageIndex=0&pageSize=5")
    r2 = client.get("/api/v1/documents?pageIndex=1&pageSize=5")
    assert r1.status_code == 200
    assert r2.status_code == 200

def test_documents_search_no_results(client):
    response = client.get("/api/v1/documents?searchQuery=XYZZYXDOESNOTEXIST")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 0
    assert data["total"] == 0

# --- W3: History Tests ---

def test_query_history_auth_required(client):
    response = client.get("/api/v1/query/history")
    assert response.status_code == 401

def test_query_history_returns_queries(client):
    tokens = _register_and_login(client, "qhist", "secret", "qhist@test.com")
    # Execute a query first — use the simple parse endpoint to seed data
    answer_resp = client.post("/api/v1/query/answer", json={"query_id": "q123", "raw_query": "Test query for history"}, headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert answer_resp.status_code == 200, f"Answer failed: {answer_resp.text}"
    response = client.get("/api/v1/query/history", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1

def test_review_history_auth_required(client):
    response = client.get("/api/v1/reviews/history")
    assert response.status_code == 401

def test_review_history_returns_reviews(client):
    tokens = _register_and_login(client, "rhist", "secret", "rhist@test.com")
    # Generate a review first
    gen_resp = client.post("/api/v1/reviews/generate", json={
        "review_id": "rev_req_1",
        "review_type": "general",
        "title": "BERT pre-training datasets",
        "query": "What datasets does BERT use?",
        "max_documents": 10
    }, headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert gen_resp.status_code == 200, f"Generate failed: {gen_resp.text}"
    response = client.get("/api/v1/reviews/history", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1

# --- W1: Rate Limiting Tests ---

def test_rate_limit_not_exceeded(client):
    for _ in range(5):
        response = client.get("/api/v1/health")
        assert response.status_code == 200

def test_graph_node_determinism(client):
    r1 = client.get("/api/v1/graph/node/doc-10")
    r2 = client.get("/api/v1/graph/node/doc-10")
    assert r1.status_code == 200
    assert r1.json() == r2.json()
