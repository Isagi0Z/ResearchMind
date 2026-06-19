def _find_node_by_id(nodes, node_id):
    return next((n for n in nodes if n["id"] == node_id), None)

def _find_edge_by_id(edges, edge_id):
    return next((e for e in edges if e["id"] == edge_id), None)


class TestGraphFiltering:
    def test_graph_filter_by_document_type(self, client):
        resp = client.get("/api/v1/graph?nodeType=document&limit=100")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["nodes"]) > 0
        assert all(n["type"] == "document" for n in data["nodes"])

    def test_graph_filter_by_entity_type(self, client):
        resp = client.get("/api/v1/graph?nodeType=entity&limit=100")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["nodes"]) > 0
        assert all(n["type"] == "entity" for n in data["nodes"])

    def test_graph_search_by_title(self, client):
        resp = client.get("/api/v1/graph?search=biology&limit=100")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["nodes"]) > 0
        doc_nodes = [n for n in data["nodes"] if n["type"] == "document"]
        assert len(doc_nodes) > 0
        assert all("biology" in (n["data"].get("title") or "").lower() for n in doc_nodes)

    def test_graph_search_no_results(self, client):
        resp = client.get("/api/v1/graph?search=XYZZYXDOESNOTEXIST&limit=100")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["nodes"]) == 0

    def test_graph_filter_and_search_combined(self, client):
        resp = client.get("/api/v1/graph?nodeType=document&search=biology&limit=100")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["nodes"]) > 0
        assert all(n["type"] == "document" for n in data["nodes"])

    def test_graph_no_filters_returns_data(self, client):
        resp = client.get("/api/v1/graph?limit=50")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["nodes"]) > 0
        assert len(data["edges"]) > 0


class TestGraphPagination:
    def test_graph_pagination_offset(self, client):
        r1 = client.get("/api/v1/graph?offset=0&limit=10")
        r2 = client.get("/api/v1/graph?offset=10&limit=10")
        assert r1.status_code == 200
        assert r2.status_code == 200
        d1 = r1.json()
        d2 = r2.json()
        assert len(d1["nodes"]) == 10
        assert len(d2["nodes"]) == 10
        ids1 = {n["id"] for n in d1["nodes"]}
        ids2 = {n["id"] for n in d2["nodes"]}
        assert ids1.isdisjoint(ids2), "page 0 and page 1 overlap"

    def test_graph_pagination_limit_ceiling(self, client):
        resp = client.get("/api/v1/graph?limit=600")
        assert resp.status_code == 422

    def test_graph_pagination_default_limit(self, client):
        resp = client.get("/api/v1/graph")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["nodes"]) <= 200

    def test_graph_pagination_negative_offset(self, client):
        resp = client.get("/api/v1/graph?offset=-1")
        assert resp.status_code == 422

    def test_graph_pagination_beyond_total(self, client):
        resp = client.get("/api/v1/graph?offset=1000000&limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["nodes"]) == 0

    def test_graph_pagination_empty_start(self, client):
        resp = client.get("/api/v1/graph?offset=0&limit=0")
        assert resp.status_code == 422


class TestGraphEdges:
    def test_graph_edges_returned(self, client):
        resp = client.get("/api/v1/graph?limit=50")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["edges"]) > 0

    def test_graph_edge_has_required_fields(self, client):
        resp = client.get("/api/v1/graph?limit=50")
        assert resp.status_code == 200
        data = resp.json()
        edge = data["edges"][0]
        assert "id" in edge
        assert "source" in edge
        assert "target" in edge
        assert "type" in edge
        assert "data" in edge
        assert "type" in edge["data"]

    def test_graph_edge_sources_and_targets_exist(self, client):
        resp = client.get("/api/v1/graph?limit=100")
        data = resp.json()
        node_ids = {n["id"] for n in data["nodes"]}
        for e in data["edges"]:
            assert e["source"] in node_ids, f"edge source {e['source']} not in node set"
            assert e["target"] in node_ids, f"edge target {e['target']} not in node set"

    def test_graph_edge_type_is_co_occurs(self, client):
        resp = client.get("/api/v1/graph?limit=100")
        data = resp.json()
        for e in data["edges"]:
            assert e["data"]["type"] == "CO_OCCURS"


class TestGraphNodeDetail:
    def test_graph_node_detail_document(self, client):
        resp = client.get("/api/v1/graph/node/doc-0")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "doc-0"
        assert data["type"] == "document"
        assert "title" in data["data"]
        assert "authors" in data["data"]

    def test_graph_node_detail_entity(self, client):
        resp = client.get("/api/v1/graph/node/ent-0-0")
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "entity"
        assert "label" in data["data"]

    def test_graph_node_detail_not_found(self, client):
        resp = client.get("/api/v1/graph/node/nonexistent")
        assert resp.status_code == 404

    def test_graph_node_detail_determinism(self, client):
        r1 = client.get("/api/v1/graph/node/doc-0")
        r2 = client.get("/api/v1/graph/node/doc-0")
        assert r1.json() == r2.json()

    def test_graph_node_detail_out_of_range(self, client):
        resp = client.get("/api/v1/graph/node/doc-999999")
        assert resp.status_code == 404
