import pytest
from backend.api.middleware import generate_request_id

def test_generate_request_id_is_deterministic():
    req1 = generate_request_id("GET", "/health")
    req2 = generate_request_id("GET", "/health")
    assert req1.startswith("req-")
    # Same inputs must produce exact same ID
    assert req1 == req2
    
def test_generate_request_id_differs_by_path():
    req1 = generate_request_id("GET", "/health")
    req2 = generate_request_id("GET", "/version")
    assert req1 != req2

@pytest.mark.parametrize("method, path", [
    ("GET", "/"),
    ("POST", "/api/v1/query"),
    ("PUT", "/random"),
    ("DELETE", "/somewhere")
])
def test_generate_request_id_formats(method, path):
    req = generate_request_id(method, path)
    assert len(req) == 12  # req- + 8 hex chars
    assert req.startswith("req-")

def test_middleware_adds_headers(client):
    response = client.get("/api/v1/health")
    assert "X-Request-ID" in response.headers
    assert "X-Process-Time" not in response.headers # Removed

def test_middleware_respects_custom_request_id(client):
    custom_id = "req-custom-id"
    response = client.get("/api/v1/health", headers={"X-Request-ID": custom_id})
    assert response.headers["X-Request-ID"] == custom_id

@pytest.mark.parametrize("i", range(5))
def test_middleware_deterministic_outputs(client, i):
    # Same route called multiple times should return same req id (if we don't supply one, and it's deterministic)
    # Wait, the client generates the same request path, so it should get the same ID
    path = f"/api/v1/health?param={i}"
    r1 = client.get(path)
    r2 = client.get(path)
    assert r1.headers["X-Request-ID"] == r2.headers["X-Request-ID"]
