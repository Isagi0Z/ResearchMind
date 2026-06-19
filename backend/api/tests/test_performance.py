"""
Performance and load validation tests.
Verifies response time budgets and pagination correctness.
"""
import time
import pytest
from fastapi.testclient import TestClient
from backend.api.app import app

client = TestClient(app)

# Response time budget in seconds per endpoint category
TIME_BUDGETS = {
    "health": 0.5,
    "query_parse": 2.0,
    "query_plan": 2.0,
    "query_route": 2.0,
    "query_answer": 5.0,
    "review_generate": 5.0,
    "review_validate": 3.0,
    "graph": 2.0,
    "documents": 2.0,
    "monitoring": 3.0,
}


def _time_request(method: str, url: str, **kwargs) -> float:
    start = time.monotonic()
    getattr(client, method)(url, **kwargs)
    return time.monotonic() - start


class TestResponseTimeBudgets:
    """Verify each endpoint responds within its time budget."""

    def test_health_speed(self):
        elapsed = _time_request("get", "/api/v1/health")
        assert elapsed < TIME_BUDGETS["health"], f"health took {elapsed:.2f}s"

    def test_query_parse_speed(self):
        elapsed = _time_request(
            "post", "/api/v1/query/parse",
            json={"raw_query": "What datasets does BERT use?"},
        )
        assert elapsed < TIME_BUDGETS["query_parse"], f"parse took {elapsed:.2f}s"

    def test_query_plan_speed(self):
        parse = client.post(
            "/api/v1/query/parse",
            json={"raw_query": "What datasets does BERT use?"},
        ).json()
        elapsed = _time_request(
            "post", "/api/v1/query/plan",
            json=parse["parsed_query"],
        )
        assert elapsed < TIME_BUDGETS["query_plan"], f"plan took {elapsed:.2f}s"

    def test_query_route_speed(self):
        parse = client.post(
            "/api/v1/query/parse",
            json={"raw_query": "What datasets does BERT use?"},
        ).json()
        plan = client.post(
            "/api/v1/query/plan",
            json=parse["parsed_query"],
        ).json()
        elapsed = _time_request(
            "post", "/api/v1/query/route",
            json=plan["execution_plan"],
        )
        assert elapsed < TIME_BUDGETS["query_route"], f"route took {elapsed:.2f}s"

    def test_query_answer_speed(self):
        elapsed = _time_request(
            "post", "/api/v1/query/answer",
            json={"query_id": "perf-q", "raw_query": "What datasets does BERT use?"},
        )
        assert elapsed < TIME_BUDGETS["query_answer"], f"answer took {elapsed:.2f}s"

    def test_review_generate_speed(self):
        elapsed = _time_request(
            "post", "/api/v1/reviews/generate",
            json={
                "review_id": "perf_rev",
                "review_type": "general",
                "title": "BERT datasets",
                "query": "What datasets does BERT use?",
                "max_documents": 10,
            },
        )
        assert elapsed < TIME_BUDGETS["review_generate"], f"review gen took {elapsed:.2f}s"

    def test_review_validate_speed(self):
        review = client.post(
            "/api/v1/reviews/generate",
            json={
                "review_id": "perf_rev_val",
                "review_type": "general",
                "title": "BERT datasets",
                "query": "What datasets does BERT use?",
                "max_documents": 10,
            },
        ).json()
        elapsed = _time_request(
            "post", "/api/v1/reviews/validate",
            json=review["review_result"],
        )
        assert elapsed < TIME_BUDGETS["review_validate"], f"review val took {elapsed:.2f}s"

    def test_graph_speed(self):
        elapsed = _time_request("get", "/api/v1/graph/data")
        assert elapsed < TIME_BUDGETS["graph"], f"graph took {elapsed:.2f}s"

    def test_documents_speed(self):
        elapsed = _time_request("get", "/api/v1/documents")
        assert elapsed < TIME_BUDGETS["documents"], f"documents took {elapsed:.2f}s"


class TestPaginationCorrectness:
    """Verify pagination returns correct slices and handles edges."""

    def test_documents_page_zero(self):
        resp = client.get("/api/v1/documents?pageIndex=0&pageSize=5")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 0
        assert len(body["data"]) <= 5

    def test_documents_page_one(self):
        r0 = client.get("/api/v1/documents?pageIndex=0&pageSize=3").json()
        r1 = client.get("/api/v1/documents?pageIndex=1&pageSize=3").json()
        # No overlap between pages
        ids_0 = {d["ruo_id"] for d in r0["data"]}
        ids_1 = {d["ruo_id"] for d in r1["data"]}
        assert ids_0.isdisjoint(ids_1), "Pages overlap"

    def test_documents_out_of_range(self):
        resp = client.get("/api/v1/documents?pageIndex=99999&pageSize=10")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 0

    def test_documents_page_size_large(self):
        resp = client.get("/api/v1/documents?pageIndex=0&pageSize=1000")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) <= 1000

    def test_consistent_total_across_pages(self):
        r0 = client.get("/api/v1/documents?pageIndex=0&pageSize=5")
        r1 = client.get("/api/v1/documents?pageIndex=1&pageSize=5")
        assert r0.json()["total"] == r1.json()["total"]


class TestLoadUnderRepeatedCalls:
    """Verify the system handles repeated calls without degradation."""

    def test_repeated_health(self):
        for _ in range(20):
            resp = client.get("/api/v1/health")
            assert resp.status_code == 200

    def test_repeated_query_parse_same(self):
        for _ in range(10):
            resp = client.post(
                "/api/v1/query/parse",
                json={"raw_query": "What datasets does BERT use?"},
            )
            assert resp.status_code == 200

    def test_determinism_with_repeated_calls(self):
        results = []
        for _ in range(5):
            resp = client.get("/api/v1/graph/data")
            results.append(resp.json())
        for i in range(1, len(results)):
            assert results[i] == results[0], f"Run {i} differs from run 0"
