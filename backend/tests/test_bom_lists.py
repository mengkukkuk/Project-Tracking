"""Saved BOM lists CRUD + authz + cross-project + cascade."""
from app.extensions import Session
from app.models import BomListItem


def _project(client, auth, **over):
    body = {"name": "Host", "status": "Pre-Sale", **over}
    return client.post("/api/projects", json=body, headers=auth).get_json()["id"]


def _bom(client, auth, pid, name):
    res = client.post(
        f"/api/projects/{pid}/records/bom",
        json={"deviceName": name, "quantity": 1, "unitPrice": 100, "totalPrice": 100},
        headers=auth,
    )
    return res.get_json()["id"]


def _register(client, email, name="Member"):
    res = client.post(
        "/api/auth/register",
        json={"name": name, "email": email, "password": "secret123"},
    )
    return {"Authorization": f"Bearer {res.get_json()['token']}"}


def test_create_bom_list_returns_summary(client, auth):
    pid = _project(client, auth, name="Alpha")
    b1 = _bom(client, auth, pid, "Sensor X")
    b2 = _bom(client, auth, pid, "PLC Y")

    res = client.post(
        "/api/bom-lists",
        json={"name": "Procurement Q3", "projectId": pid, "itemIds": [b1, b2]},
        headers=auth,
    )
    assert res.status_code == 201, res.get_json()
    body = res.get_json()
    assert body["name"] == "Procurement Q3"
    assert body["projectId"] == pid
    assert body["projectName"] == "Alpha"
    assert body["itemCount"] == 2
    assert body["ownerId"]


def test_get_bom_list_detail_includes_items_with_project_name(client, auth):
    p1 = _project(client, auth, name="Alpha")
    p2 = _project(client, auth, name="Beta")
    # Source items from two different projects -> cross-project list
    b1 = _bom(client, auth, p1, "Camera VC-200")
    b2 = _bom(client, auth, p2, "Drive SD-300")

    lid = client.post(
        "/api/bom-lists",
        json={"name": "Mixed", "projectId": p1, "itemIds": [b1, b2]},
        headers=auth,
    ).get_json()["id"]

    body = client.get(f"/api/bom-lists/{lid}", headers=auth).get_json()
    assert body["itemCount"] == 2
    by_name = {it["deviceName"]: it for it in body["items"]}
    assert by_name["Camera VC-200"]["projectName"] == "Alpha"
    assert by_name["Drive SD-300"]["projectName"] == "Beta"


def test_list_bom_lists_summary_form(client, auth):
    pid = _project(client, auth)
    b1 = _bom(client, auth, pid, "X")
    client.post(
        "/api/bom-lists",
        json={"name": "L1", "projectId": pid, "itemIds": [b1]},
        headers=auth,
    )
    items = client.get("/api/bom-lists", headers=auth).get_json()["items"]
    assert len(items) == 1
    # Summary form: no expanded items[]
    assert "items" not in items[0]
    assert items[0]["itemCount"] == 1


def test_patch_rename_and_replace_items(client, auth):
    pid = _project(client, auth, name="P")
    b1, b2, b3 = (_bom(client, auth, pid, n) for n in ("A", "B", "C"))
    lid = client.post(
        "/api/bom-lists",
        json={"name": "Initial", "projectId": pid, "itemIds": [b1, b2]},
        headers=auth,
    ).get_json()["id"]

    res = client.patch(
        f"/api/bom-lists/{lid}",
        json={"name": "Renamed", "itemIds": [b2, b3]},
        headers=auth,
    )
    assert res.status_code == 200, res.get_json()
    body = res.get_json()
    assert body["name"] == "Renamed"
    assert body["itemCount"] == 2

    detail = client.get(f"/api/bom-lists/{lid}", headers=auth).get_json()
    assert {it["deviceName"] for it in detail["items"]} == {"B", "C"}


def test_patch_authz_non_owner_403(client, auth):
    pid = _project(client, auth)
    b1 = _bom(client, auth, pid, "X")
    lid = client.post(
        "/api/bom-lists",
        json={"name": "Mine", "projectId": pid, "itemIds": [b1]},
        headers=auth,
    ).get_json()["id"]

    member = _register(client, "member@x.com")
    res = client.patch(f"/api/bom-lists/{lid}", json={"name": "Hijack"}, headers=member)
    assert res.status_code == 403


def test_delete_authz_and_cascade(client, auth):
    pid = _project(client, auth)
    b1, b2 = (_bom(client, auth, pid, n) for n in ("A", "B"))
    lid = client.post(
        "/api/bom-lists",
        json={"name": "Doomed", "projectId": pid, "itemIds": [b1, b2]},
        headers=auth,
    ).get_json()["id"]

    member = _register(client, "member2@x.com")
    assert client.delete(f"/api/bom-lists/{lid}", headers=member).status_code == 403
    assert client.delete(f"/api/bom-lists/{lid}", headers=auth).status_code == 204
    # Cascade: list-item rows are gone
    assert Session.query(BomListItem).filter_by(list_id=lid).count() == 0


def test_source_row_delete_cascades_into_list_items(client, auth):
    pid = _project(client, auth)
    b1, b2 = (_bom(client, auth, pid, n) for n in ("A", "B"))
    lid = client.post(
        "/api/bom-lists",
        json={"name": "L", "projectId": pid, "itemIds": [b1, b2]},
        headers=auth,
    ).get_json()["id"]

    # Delete the source BOM row -> the list-item should be cascaded away
    assert client.delete(f"/api/records/bom/{b1}", headers=auth).status_code == 204

    detail = client.get(f"/api/bom-lists/{lid}", headers=auth).get_json()
    assert detail["itemCount"] == 1
    assert {it["deviceName"] for it in detail["items"]} == {"B"}


def test_create_with_unknown_bom_id_422(client, auth):
    pid = _project(client, auth)
    res = client.post(
        "/api/bom-lists",
        json={"name": "Bogus", "projectId": pid, "itemIds": [999999]},
        headers=auth,
    )
    assert res.status_code == 422


def test_create_with_unknown_project_422(client, auth):
    res = client.post(
        "/api/bom-lists",
        json={"name": "Bogus", "projectId": 999999, "itemIds": []},
        headers=auth,
    )
    assert res.status_code == 422


def test_endpoints_require_auth(client):
    assert client.get("/api/bom-lists").status_code == 401
    assert client.get("/api/bom-lists/1").status_code == 401
    assert client.post("/api/bom-lists", json={}).status_code == 401
