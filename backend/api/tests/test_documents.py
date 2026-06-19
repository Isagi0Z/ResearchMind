class TestDocumentListing:
    def test_documents_default_pagination(self, client):
        resp = client.get("/api/v1/documents")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "total" in data
        assert len(data["data"]) <= 10

    def test_documents_returns_items(self, client):
        resp = client.get("/api/v1/documents?pageSize=50")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) > 0
        assert data["total"] > 0

    def test_documents_item_shape(self, client):
        resp = client.get("/api/v1/documents?pageSize=1")
        data = resp.json()
        item = data["data"][0]
        assert "ruo_id" in item
        assert "title" in item
        assert "authors" in item
        assert "year" in item
        assert "status" in item
        assert "entity_count" in item

    def test_documents_page_size_ceiling(self, client):
        resp = client.get("/api/v1/documents?pageSize=2000")
        assert resp.status_code == 422

    def test_documents_page_size_zero(self, client):
        resp = client.get("/api/v1/documents?pageSize=0")
        assert resp.status_code == 422


class TestDocumentSearch:
    def test_search_by_title_fragment(self, client):
        resp = client.get("/api/v1/documents?searchQuery=Research&pageSize=50")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) > 0
        for item in data["data"]:
            assert "research" in item["title"].lower()

    def test_search_no_results(self, client):
        resp = client.get("/api/v1/documents?searchQuery=XYZZYXDOESNOTEXIST")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 0
        assert data["total"] == 0

    def test_search_empty_query(self, client):
        resp = client.get("/api/v1/documents?searchQuery=")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) >= 0

    def test_search_case_insensitive(self, client):
        resp = client.get("/api/v1/documents?searchQuery=research&pageSize=50")
        resp2 = client.get("/api/v1/documents?searchQuery=RESEARCH&pageSize=50")
        assert resp.json()["total"] == resp2.json()["total"]


class TestDocumentSort:
    def test_sort_by_title_asc(self, client):
        resp = client.get("/api/v1/documents?sortBy=title&sortDirection=asc&pageSize=50")
        assert resp.status_code == 200
        data = resp.json()
        titles = [item["title"].lower() for item in data["data"]]
        assert titles == sorted(titles)

    def test_sort_by_title_desc(self, client):
        resp = client.get("/api/v1/documents?sortBy=title&sortDirection=desc&pageSize=50")
        assert resp.status_code == 200
        data = resp.json()
        titles = [item["title"].lower() for item in data["data"]]
        assert titles == sorted(titles, reverse=True)

    def test_sort_by_year_asc(self, client):
        resp = client.get("/api/v1/documents?sortBy=year&sortDirection=asc&pageSize=50")
        assert resp.status_code == 200
        data = resp.json()
        years = [item["year"] or 0 for item in data["data"]]
        assert years == sorted(years)

    def test_sort_by_year_desc(self, client):
        resp = client.get("/api/v1/documents?sortBy=year&sortDirection=desc&pageSize=50")
        assert resp.status_code == 200
        data = resp.json()
        years = [item["year"] or 0 for item in data["data"]]
        assert years == sorted(years, reverse=True)

    def test_sort_with_search(self, client):
        resp = client.get("/api/v1/documents?searchQuery=biology&sortBy=year&sortDirection=asc&pageSize=50")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) > 0
        years = [item["year"] or 0 for item in data["data"]]
        assert years == sorted(years)


class TestDocumentPagination:
    def test_pagination_offset(self, client):
        r1 = client.get("/api/v1/documents?pageIndex=0&pageSize=10")
        r2 = client.get("/api/v1/documents?pageIndex=1&pageSize=10")
        assert r1.status_code == 200
        assert r2.status_code == 200
        d1 = r1.json()
        d2 = r2.json()
        ids1 = {item["ruo_id"] for item in d1["data"]}
        ids2 = {item["ruo_id"] for item in d2["data"]}
        assert ids1.isdisjoint(ids2)

    def test_pagination_pages_have_correct_size(self, client):
        resp = client.get("/api/v1/documents?pageIndex=0&pageSize=7")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) <= 7

    def test_pagination_beyond_total(self, client):
        resp = client.get("/api/v1/documents?pageIndex=1000000&pageSize=10")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 0

    def test_pagination_consistency(self, client):
        total_resp = client.get("/api/v1/documents?pageSize=1000")
        total = total_resp.json()["total"]
        count_resp = client.get("/api/v1/documents?pageSize=1")
        count = count_resp.json()["total"]
        assert total == count


class TestDocumentDetail:
    def test_document_detail_by_id(self, client):
        list_resp = client.get("/api/v1/documents?pageSize=1")
        ruo_id = list_resp.json()["data"][0]["ruo_id"]
        resp = client.get(f"/api/v1/documents/{ruo_id}")
        assert resp.status_code == 200
        detail = resp.json()
        assert detail["ruo_id"] == ruo_id
        assert "title" in detail
        assert "authors" in detail
        assert "year" in detail

    def test_document_detail_not_found(self, client):
        resp = client.get("/api/v1/documents/nonexistent-id")
        assert resp.status_code == 404

    def test_document_detail_has_all_fields(self, client):
        list_resp = client.get("/api/v1/documents?pageSize=1")
        ruo_id = list_resp.json()["data"][0]["ruo_id"]
        resp = client.get(f"/api/v1/documents/{ruo_id}")
        detail = resp.json()
        assert "ruo_id" in detail
        assert "title" in detail
        assert "authors" in detail
        assert "year" in detail
        assert "status" in detail
        assert "entity_count" in detail
        assert "source" in detail
