import pytest
from fastapi.testclient import TestClient
from backend.api.app import app

client = TestClient(app)

def test_e2e_query_flow():
    # A. Parse Query
    parse_resp1 = client.post("/api/v1/query/parse", json={"raw_query": "What datasets does BERT use?"})
    assert parse_resp1.status_code == 200
    parsed_query = parse_resp1.json()["parsed_query"]
    
    # B. Create Plan
    plan_resp1 = client.post("/api/v1/query/plan", json=parsed_query)
    assert plan_resp1.status_code == 200
    execution_plan = plan_resp1.json()["execution_plan"]
    
    # C. Route Plan
    route_resp1 = client.post("/api/v1/query/route", json=execution_plan)
    assert route_resp1.status_code == 200
    step_routes = route_resp1.json()["step_routes"]
    
    # D. Answer Query
    answer_resp1 = client.post("/api/v1/query/answer", json={"query_id": "q123", "raw_query": "What datasets does BERT use?"})
    assert answer_resp1.status_code == 200
    answer_result1 = answer_resp1.json()
    
    # Determinism Verification - Run A-D again and compare
    parse_resp2 = client.post("/api/v1/query/parse", json={"raw_query": "What datasets does BERT use?"})
    assert parse_resp1.json() == parse_resp2.json()
    
    plan_resp2 = client.post("/api/v1/query/plan", json=parsed_query)
    assert plan_resp1.json() == plan_resp2.json()
    
    route_resp2 = client.post("/api/v1/query/route", json=execution_plan)
    assert route_resp1.json() == route_resp2.json()
    
    answer_resp2 = client.post("/api/v1/query/answer", json={"query_id": "q123", "raw_query": "What datasets does BERT use?"})
    assert answer_result1 == answer_resp2.json()
    
    assert answer_result1["parsed_query"]["query_type"] == "FACTUAL"

def test_e2e_review_flow():
    # E. Generate Review
    review_req = {
        "review_id": "rev_req_1",
        "review_type": "general",
        "title": "BERT pre-training datasets",
        "query": "What datasets does BERT use?",
        "max_documents": 10
    }
    
    gen_resp1 = client.post("/api/v1/reviews/generate", json=review_req)
    assert gen_resp1.status_code == 200
    review_result1 = gen_resp1.json()["review_result"]
    
    # F. Validate Review
    val_resp1 = client.post("/api/v1/reviews/validate", json=review_result1)
    assert val_resp1.status_code == 200
    trace_report1 = val_resp1.json()["traceability_report"]
    
    # Determinism Verification
    gen_resp2 = client.post("/api/v1/reviews/generate", json=review_req)
    assert review_result1 == gen_resp2.json()["review_result"]
    
    val_resp2 = client.post("/api/v1/reviews/validate", json=review_result1)
    assert trace_report1 == val_resp2.json()["traceability_report"]

if __name__ == "__main__":
    test_e2e_query_flow()
    test_e2e_review_flow()
    print("E2E tests passed and deterministic!")
