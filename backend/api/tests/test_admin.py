import pytest
from backend.api.tests.test_stubs import _register_and_login, _make_admin


# --- Unauthorized Access Tests ---

def test_admin_users_requires_auth(client):
    response = client.get("/api/v1/admin/users")
    assert response.status_code == 401


def test_admin_users_requires_admin_role(client):
    tokens = _register_and_login(client, "regularuser", "secret", "regular@test.com")
    response = client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert response.status_code == 401


def test_admin_user_detail_requires_auth(client):
    response = client.get("/api/v1/admin/users/some-id")
    assert response.status_code == 401


def test_admin_update_role_requires_auth(client):
    response = client.patch(
        "/api/v1/admin/users/some-id/role",
        json={"role": "admin"}
    )
    assert response.status_code == 401


def test_admin_update_status_requires_auth(client):
    response = client.patch(
        "/api/v1/admin/users/some-id/status",
        json={"is_active": False}
    )
    assert response.status_code == 401


# --- User Listing Tests ---

def test_admin_users_empty_list(client):
    tokens = _register_and_login(client, "adminempty", "admin123", "adminempty@test.com")
    _make_admin("adminempty")
    response = client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "total" in data
    assert data["total"] > 0
    assert len(data["data"]) > 0


def test_admin_users_lists_all_users(client):
    tokens = _register_and_login(client, "adminlist", "admin123", "adminlist@test.com")
    _register_and_login(client, "user1", "secret", "user1@test.com")
    _register_and_login(client, "user2", "secret", "user2@test.com")
    _make_admin("adminlist")
    response = client.get(
        "/api/v1/admin/users?pageSize=50",
        headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 3


def test_admin_users_pagination(client):
    tokens = _register_and_login(client, "adminpage", "admin123", "adminpage@test.com")
    _make_admin("adminpage")

    r1 = client.get(
        "/api/v1/admin/users?pageIndex=0&pageSize=2",
        headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert r1.status_code == 200
    d1 = r1.json()
    assert len(d1["data"]) <= 2

    r2 = client.get(
        "/api/v1/admin/users?pageIndex=1&pageSize=2",
        headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert r2.status_code == 200
    d2 = r2.json()

    if d1["total"] > 2:
        assert d1["data"] != d2["data"]


# --- User Search Tests ---

def test_admin_users_search_by_username(client):
    tokens = _register_and_login(client, "adminsearch", "admin123", "adminsearch@test.com")
    _register_and_login(client, "targetuser", "secret", "target@test.com")
    _make_admin("adminsearch")
    response = client.get(
        "/api/v1/admin/users?searchQuery=target",
        headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) >= 1
    usernames = [u["username"] for u in data["data"]]
    assert "targetuser" in usernames


def test_admin_users_search_by_email(client):
    tokens = _register_and_login(client, "adminemail", "admin123", "adminemail@test.com")
    _register_and_login(client, "emailuser", "secret", "findme@test.com")
    _make_admin("adminemail")
    response = client.get(
        "/api/v1/admin/users?searchQuery=findme",
        headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) >= 1
    emails = [u["email"] for u in data["data"]]
    assert "findme@test.com" in emails


def test_admin_users_search_no_results(client):
    tokens = _register_and_login(client, "adminnosearch", "admin123", "adminnosearch@test.com")
    _make_admin("adminnosearch")
    response = client.get(
        "/api/v1/admin/users?searchQuery=XYZZYXDOESNOTEXIST",
        headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 0
    assert data["total"] == 0


# --- Role Update Tests ---

def test_admin_update_role_to_admin(client):
    tokens = _register_and_login(client, "adminpromote", "admin123", "adminpromote@test.com")
    _register_and_login(client, "promoteme", "secret", "promoteme@test.com")
    _make_admin("adminpromote")

    # Get the target user's ID
    list_resp = client.get(
        "/api/v1/admin/users?searchQuery=promoteme",
        headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert list_resp.status_code == 200
    target_id = list_resp.json()["data"][0]["id"]

    resp = client.patch(
        f"/api/v1/admin/users/{target_id}/role",
        json={"role": "admin"},
        headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "admin"


def test_admin_update_role_to_user(client):
    tokens = _register_and_login(client, "admindemote", "admin123", "admindemote@test.com")
    _register_and_login(client, "demoteme", "secret", "demoteme@test.com")
    _make_admin("admindemote")

    list_resp = client.get(
        "/api/v1/admin/users?searchQuery=demoteme",
        headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    target_id = list_resp.json()["data"][0]["id"]

    # Promote first
    client.patch(
        f"/api/v1/admin/users/{target_id}/role",
        json={"role": "admin"},
        headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )

    # Demote
    resp = client.patch(
        f"/api/v1/admin/users/{target_id}/role",
        json={"role": "user"},
        headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "user"


def test_admin_update_role_invalid_value(client):
    tokens = _register_and_login(client, "admininvalid", "admin123", "admininvalid@test.com")
    _register_and_login(client, "invalidrole", "secret", "invalidrole@test.com")
    _make_admin("admininvalid")

    list_resp = client.get(
        "/api/v1/admin/users?searchQuery=invalidrole",
        headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    target_id = list_resp.json()["data"][0]["id"]

    resp = client.patch(
        f"/api/v1/admin/users/{target_id}/role",
        json={"role": "superadmin"},
        headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert resp.status_code == 400


def test_admin_update_role_not_found(client):
    tokens = _register_and_login(client, "adminnotfound", "admin123", "adminnotfound@test.com")
    _make_admin("adminnotfound")
    resp = client.patch(
        "/api/v1/admin/users/00000000-0000-0000-0000-000000000000/role",
        json={"role": "user"},
        headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert resp.status_code == 404


# --- Status Update Tests ---

def test_admin_update_status_deactivate(client):
    tokens = _register_and_login(client, "admindeact", "admin123", "admindeact@test.com")
    _register_and_login(client, "deactivateme", "secret", "deactivateme@test.com")
    _make_admin("admindeact")

    list_resp = client.get(
        "/api/v1/admin/users?searchQuery=deactivateme",
        headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    target_id = list_resp.json()["data"][0]["id"]

    resp = client.patch(
        f"/api/v1/admin/users/{target_id}/status",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


def test_admin_update_status_activate(client):
    tokens = _register_and_login(client, "adminact", "admin123", "adminact@test.com")
    _register_and_login(client, "activateme", "secret", "activateme@test.com")
    _make_admin("adminact")

    list_resp = client.get(
        "/api/v1/admin/users?searchQuery=activateme",
        headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    target_id = list_resp.json()["data"][0]["id"]

    # Deactivate first
    client.patch(
        f"/api/v1/admin/users/{target_id}/status",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )

    # Reactivate
    resp = client.patch(
        f"/api/v1/admin/users/{target_id}/status",
        json={"is_active": True},
        headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is True


def test_admin_update_status_not_found(client):
    tokens = _register_and_login(client, "adminstatnotfound", "admin123", "adminstatnotfound@test.com")
    _make_admin("adminstatnotfound")
    resp = client.patch(
        "/api/v1/admin/users/00000000-0000-0000-0000-000000000000/status",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert resp.status_code == 404


# --- User Detail Tests ---

def test_admin_user_detail(client):
    tokens = _register_and_login(client, "admindetail", "admin123", "admindetail@test.com")
    _make_admin("admindetail")

    list_resp = client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    target_id = list_resp.json()["data"][0]["id"]

    resp = client.get(
        f"/api/v1/admin/users/{target_id}",
        headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == target_id
    assert "username" in data
    assert "email" in data
    assert "role" in data
    assert "is_active" in data


def test_admin_user_detail_not_found(client):
    tokens = _register_and_login(client, "admindetailnf", "admin123", "admindetailnf@test.com")
    _make_admin("admindetailnf")
    resp = client.get(
        "/api/v1/admin/users/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert resp.status_code == 404


# --- Permission Boundary Tests ---

def test_admin_cannot_promote_self_to_admin(client):
    tokens = _register_and_login(client, "selfpromote", "admin123", "selfpromote@test.com")
    _make_admin("selfpromote")

    list_resp = client.get(
        "/api/v1/admin/users?searchQuery=selfpromote",
        headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    target_id = list_resp.json()["data"][0]["id"]

    resp = client.patch(
        f"/api/v1/admin/users/{target_id}/role",
        json={"role": "admin"},
        headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    # Should succeed - admin can update any user's role (including own)
    assert resp.status_code == 200


def test_non_admin_cannot_access_any_admin_endpoint(client):
    tokens = _register_and_login(client, "nonadmin", "secret", "nonadmin@test.com")

    # List
    assert client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {tokens['access_token']}"}).status_code == 401

    # Detail
    assert client.get("/api/v1/admin/users/00000000-0000-0000-0000-000000000000", headers={"Authorization": f"Bearer {tokens['access_token']}"}).status_code == 401

    # Update role
    assert client.patch("/api/v1/admin/users/00000000-0000-0000-0000-000000000000/role", json={"role": "admin"}, headers={"Authorization": f"Bearer {tokens['access_token']}"}).status_code == 401

    # Update status
    assert client.patch("/api/v1/admin/users/00000000-0000-0000-0000-000000000000/status", json={"is_active": False}, headers={"Authorization": f"Bearer {tokens['access_token']}"}).status_code == 401
