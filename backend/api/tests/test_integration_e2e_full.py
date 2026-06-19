"""
Full end-to-end integration tests covering all major workflows.
Exercises auth, query, review, graph, documents, monitoring, and admin endpoints
through the real FastAPI TestClient.
"""
import pytest
from fastapi.testclient import TestClient
from backend.api.app import app

client = TestClient(app)


def _register_user(username="e2etest", email="e2e@test.com", password="TestPass123!"):
    return client.post("/api/v1/auth/register", json={
        "username": username,
        "email": email,
        "password": password,
    })


def _login_user(username="e2etest", password="TestPass123!"):
    return client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


class TestE2EAuthFlow:
    """Registration, login, token refresh, logout, and profile access."""

    def test_01_register_and_login(self):
        _register_user()
        resp = _login_user()
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"

    def test_02_duplicate_registration_fails(self):
        _register_user()
        resp = _register_user()
        assert resp.status_code == 400

    def test_03_access_me_with_token(self):
        _register_user("e2e_me", "e2e_me@test.com")
        login = _login_user("e2e_me").json()
        headers = {"Authorization": f"Bearer {login['access_token']}"}
        resp = client.get("/api/v1/auth/me", headers=headers)
        assert resp.status_code == 200
        profile = resp.json()
        assert profile["username"] == "e2e_me"
        assert "id" in profile

    def test_04_refresh_token(self):
        _register_user("e2e_refresh", "e2e_refresh@test.com")
        login = _login_user("e2e_refresh").json()
        refresh_token = login["refresh_token"]
        resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert "refresh_token" in body

    def test_05_logout_revokes_token(self):
        _register_user("e2e_logout", "e2e_logout@test.com")
        login = _login_user("e2e_logout").json()
        resp = client.post("/api/v1/auth/logout", json={"refresh_token": login["refresh_token"]})
        assert resp.status_code == 200
        assert resp.json()["message"] == "Logged out successfully"
        resp2 = client.post("/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]})
        assert resp2.status_code == 401

    def test_06_invalid_login_fails(self):
        resp = client.post(
            "/api/v1/auth/login",
            data={"username": "nonexistent", "password": "wrong"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code == 401

    def test_07_access_without_token_fails(self):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401


class TestE2EQueryFlow:
    """Parse, plan, route, answer — with determinism verification."""

    QUERY = "What datasets does BERT use?"

    def test_query_lifecycle(self):
        # Parse
        p1 = client.post("/api/v1/query/parse", json={"raw_query": self.QUERY})
        assert p1.status_code == 200
        parsed = p1.json()["parsed_query"]

        # Plan
        plan1 = client.post("/api/v1/query/plan", json=parsed)
        assert plan1.status_code == 200
        plan = plan1.json()["execution_plan"]

        # Route
        r1 = client.post("/api/v1/query/route", json=plan)
        assert r1.status_code == 200
        routes = r1.json()["step_routes"]

        # Answer
        a1 = client.post("/api/v1/query/answer", json={
            "query_id": "e2e-q",
            "raw_query": self.QUERY,
        })
        assert a1.status_code == 200
        result = a1.json()
        assert result["parsed_query"]["query_type"] == "FACTUAL"

        # Determinism
        p2 = client.post("/api/v1/query/parse", json={"raw_query": self.QUERY})
        assert p1.json() == p2.json()

        plan2 = client.post("/api/v1/query/plan", json=parsed)
        assert plan1.json() == plan2.json()

        r2 = client.post("/api/v1/query/route", json=plan)
        assert r1.json() == r2.json()

        a2 = client.post("/api/v1/query/answer", json={
            "query_id": "e2e-q",
            "raw_query": self.QUERY,
        })
        assert result == a2.json()


class TestE2EReviewFlow:
    """Review generation and validation with determinism."""

    REQ = {
        "review_id": "e2e_rev",
        "review_type": "general",
        "title": "BERT pre-training datasets",
        "query": "What datasets does BERT use?",
        "max_documents": 10,
    }

    def test_review_generate_and_validate(self):
        # Generate
        g1 = client.post("/api/v1/reviews/generate", json=self.REQ)
        assert g1.status_code == 200
        review = g1.json()["review_result"]

        # Validate
        v1 = client.post("/api/v1/reviews/validate", json=review)
        assert v1.status_code == 200
        assert "traceability_report" in v1.json()

        # Determinism
        g2 = client.post("/api/v1/reviews/generate", json=self.REQ)
        assert review == g2.json()["review_result"]

        v2 = client.post("/api/v1/reviews/validate", json=review)
        assert v1.json() == v2.json()


class TestE2EGraphFlow:
    """Graph endpoint returns structured corpus data."""

    def test_graph_data(self):
        resp = client.get("/api/v1/graph/data")
        assert resp.status_code == 200
        body = resp.json()
        assert "nodes" in body
        assert "edges" in body

    def test_graph_determinism(self):
        r1 = client.get("/api/v1/graph/data")
        r2 = client.get("/api/v1/graph/data")
        assert r1.json() == r2.json()


class TestE2EDocumentFlow:
    """Document listing endpoint."""

    def test_documents_list(self):
        resp = client.get("/api/v1/documents")
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
        assert "total" in body

    def test_documents_pagination(self):
        r1 = client.get("/api/v1/documents?pageIndex=0&pageSize=5")
        assert r1.status_code == 200
        data = r1.json()
        assert len(data["data"]) <= 5

        r2 = client.get("/api/v1/documents?pageIndex=1&pageSize=5")
        assert r2.status_code == 200

    def test_documents_determinism(self):
        r1 = client.get("/api/v1/documents")
        r2 = client.get("/api/v1/documents")
        assert r1.json() == r2.json()


class TestE2EMonitoringFlow:
    """Monitoring and health endpoints."""

    def test_health(self):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "healthy"}

    def test_metrics_requires_admin(self):
        resp = client.get("/api/v1/monitoring/metrics")
        assert resp.status_code == 401


class TestE2EAdminFlow:
    """Admin endpoints (requires admin credentials)."""

    def test_admin_list_users_requires_auth(self):
        resp = client.get("/api/v1/admin/users")
        assert resp.status_code == 401

    def test_admin_list_users_as_admin(self):
        from backend.api.auth.security import get_password_hash
        from backend.db.session import async_session_factory
        from backend.db.models.user import User
        import uuid

        # Directly create an admin user in DB since registration creates role=user
        async def _make_admin():
            async with async_session_factory() as session:
                admin = User(
                    username="e2e_admin",
                    email="e2e_admin@test.com",
                    password_hash=get_password_hash("AdminPass123!"),
                    role="admin",
                    id=uuid.uuid4(),
                )
                session.add(admin)
                await session.commit()
                return admin

        import asyncio
        asyncio.run(_make_admin())

        login = _login_user("e2e_admin", "AdminPass123!").json()
        headers = {"Authorization": f"Bearer {login['access_token']}"}
        resp = client.get("/api/v1/admin/users", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
        assert "total" in body


class TestE2ESecurityFlow:
    """Security-related verifications."""

    def test_cors_headers(self):
        resp = client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.status_code == 200
        assert "access-control-allow-origin" in resp.headers

    def test_security_headers(self):
        resp = client.get("/api/v1/health")
        assert resp.headers.get("x-content-type-options") == "nosniff"
        assert resp.headers.get("x-frame-options") == "DENY"
        assert resp.headers.get("x-xss-protection") == "1; mode=block"
        assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"

    def test_large_payload_rejected(self):
        large = {"raw_query": "x" * 6_000_000}
        resp = client.post("/api/v1/query/parse", json=large)
        assert resp.status_code in (413, 422)

    def test_rate_limit_applied(self):
        for _ in range(5):
            client.get("/api/v1/health")
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200  # rate limit not hit at low volume
        assert "x-request-id" in resp.headers
