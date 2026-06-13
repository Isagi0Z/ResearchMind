def test_health_check(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_version(client):
    response = client.get("/api/v1/version")
    assert response.status_code == 200
    assert "version" in response.json()

def test_openapi_generation(client):
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert "info" in data
    assert data["info"]["title"] == "ResearchMind API"
    assert "paths" in data

def test_docs(client):
    response = client.get("/api/v1/docs")
    assert response.status_code == 200

def test_redoc(client):
    response = client.get("/api/v1/redoc")
    assert response.status_code == 200
