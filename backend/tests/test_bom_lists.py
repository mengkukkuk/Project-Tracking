"""Saved BOM lists CRUD + authz + quantities + cascade.

Lists select entries from the read-only `inventory` catalogue and attach a
quantity to each. The catalogue has no POST endpoint, so fixtures insert rows
via the Session directly.
"""
from app.extensions import Session
from app.models import BomListItem, Inventory


def _project(client, auth, **over):
    body = {"name": "Host", "status": "Pre-Sale", **over}
    return client.post("/api/projects", json=body, headers=auth).get_json()["id"]


def _inventory(name, unit_price=100, **over):
    """Insert a catalogue entry directly — /api/inventory is read-only."""
    row = Inventory(device_name=name, unit_price=unit_price, **over)
    Session.add(row)
    Session.commit()
    return row.id


def _register(client, email, name="Member"):
    res = client.post(
        "/api/auth/register",
        json={"name": name, "email": email, "password": "secret123"},
    )
    return {"Authorization": f"Bearer {res.get_json()['token']}"}


def test_create_bom_list_returns_summary(client, auth):
    pid = _project(client, auth, name="Alpha")
    i1 = _inventory("Sensor X")
    i2 = _inventory("PLC Y")

    res = client.post(
        "/api/bom-lists",
        json={
            "name": "Procurement Q3",
            "projectId": pid,
            "items": [{"inventoryId": i1, "quantity": 2}, {"inventoryId": i2}],
        },
        headers=auth,
    )
    assert res.status_code == 201, res.get_json()
    body = res.get_json()
    assert body["name"] == "Procurement Q3"
    assert body["projectId"] == pid
    assert body["projectName"] == "Alpha"
    assert body["itemCount"] == 2
    assert body["ownerId"]


def test_detail_items_carry_quantity_and_derived_total(client, auth):
    pid = _project(client, auth, name="Alpha")
    i1 = _inventory("Camera VC-200", unit_price=1500)
    i2 = _inventory("Drive SD-300", unit_price=250)

    lid = client.post(
        "/api/bom-lists",
        json={
            "name": "Mixed",
            "projectId": pid,
            "items": [{"inventoryId": i1, "quantity": 3}, {"inventoryId": i2, "quantity": 1}],
        },
        headers=auth,
    ).get_json()["id"]

    body = client.get(f"/api/bom-lists/{lid}", headers=auth).get_json()
    assert body["itemCount"] == 2
    by_name = {it["deviceName"]: it for it in body["items"]}
    assert by_name["Camera VC-200"]["quantity"] == 3
    assert by_name["Camera VC-200"]["totalPrice"] == 4500  # 3 x 1500
    assert by_name["Drive SD-300"]["totalPrice"] == 250
    # A catalogue entry is project-independent -- no source project leaks in.
    assert "projectName" not in by_name["Camera VC-200"]


def test_detail_unpriced_entry_yields_null_total(client, auth):
    pid = _project(client, auth)
    i1 = _inventory("Unpriced", unit_price=None)
    lid = client.post(
        "/api/bom-lists",
        json={"name": "L", "projectId": pid, "items": [{"inventoryId": i1, "quantity": 4}]},
        headers=auth,
    ).get_json()["id"]

    item = client.get(f"/api/bom-lists/{lid}", headers=auth).get_json()["items"][0]
    assert item["quantity"] == 4
    assert item["totalPrice"] is None


def test_quantity_defaults_to_one(client, auth):
    pid = _project(client, auth)
    i1 = _inventory("Defaulted", unit_price=70)
    lid = client.post(
        "/api/bom-lists",
        json={"name": "L", "projectId": pid, "items": [{"inventoryId": i1}]},
        headers=auth,
    ).get_json()["id"]

    item = client.get(f"/api/bom-lists/{lid}", headers=auth).get_json()["items"][0]
    assert item["quantity"] == 1
    assert item["totalPrice"] == 70


def test_quantity_below_one_is_422(client, auth):
    pid = _project(client, auth)
    i1 = _inventory("X")
    for bad in (0, -3):
        res = client.post(
            "/api/bom-lists",
            json={
                "name": "L",
                "projectId": pid,
                "items": [{"inventoryId": i1, "quantity": bad}],
            },
            headers=auth,
        )
        assert res.status_code == 422, bad


def test_duplicate_inventory_ids_collapse_last_wins(client, auth):
    pid = _project(client, auth)
    i1 = _inventory("Dupe", unit_price=10)
    lid = client.post(
        "/api/bom-lists",
        json={
            "name": "L",
            "projectId": pid,
            "items": [{"inventoryId": i1, "quantity": 2}, {"inventoryId": i1, "quantity": 5}],
        },
        headers=auth,
    ).get_json()["id"]

    # (list_id, inventory_id) is the composite PK, so the dupe must collapse.
    items = client.get(f"/api/bom-lists/{lid}", headers=auth).get_json()["items"]
    assert len(items) == 1
    assert items[0]["quantity"] == 5


def test_list_bom_lists_summary_form(client, auth):
    pid = _project(client, auth)
    i1 = _inventory("X")
    client.post(
        "/api/bom-lists",
        json={"name": "L1", "projectId": pid, "items": [{"inventoryId": i1}]},
        headers=auth,
    )
    items = client.get("/api/bom-lists", headers=auth).get_json()["items"]
    assert len(items) == 1
    # Summary form: no expanded items[]
    assert "items" not in items[0]
    assert items[0]["itemCount"] == 1


def test_patch_rename_and_replace_items(client, auth):
    pid = _project(client, auth, name="P")
    i1, i2, i3 = (_inventory(n) for n in ("A", "B", "C"))
    lid = client.post(
        "/api/bom-lists",
        json={
            "name": "Initial",
            "projectId": pid,
            "items": [{"inventoryId": i1}, {"inventoryId": i2}],
        },
        headers=auth,
    ).get_json()["id"]

    res = client.patch(
        f"/api/bom-lists/{lid}",
        json={"name": "Renamed", "items": [{"inventoryId": i2}, {"inventoryId": i3}]},
        headers=auth,
    )
    assert res.status_code == 200, res.get_json()
    body = res.get_json()
    assert body["name"] == "Renamed"
    assert body["itemCount"] == 2

    detail = client.get(f"/api/bom-lists/{lid}", headers=auth).get_json()
    assert {it["deviceName"] for it in detail["items"]} == {"B", "C"}


def test_patch_preserves_item_quantities(client, auth):
    """A rename must never disturb quantities.

    save() on the client always resends the FULL selection and _replace_items
    clears and rebuilds, so this pins both halves: an absent "items" key leaves
    rows alone, and a resent payload round-trips its quantities intact.
    """
    pid = _project(client, auth)
    i1, i2, i3 = (_inventory(n, unit_price=10) for n in ("A", "B", "C"))
    payload = [
        {"inventoryId": i1, "quantity": 1},
        {"inventoryId": i2, "quantity": 2},
        {"inventoryId": i3, "quantity": 6},
    ]
    lid = client.post(
        "/api/bom-lists",
        json={"name": "Quantities", "projectId": pid, "items": payload},
        headers=auth,
    ).get_json()["id"]

    def quantities():
        detail = client.get(f"/api/bom-lists/{lid}", headers=auth).get_json()
        return {it["deviceName"]: it["quantity"] for it in detail["items"]}

    assert quantities() == {"A": 1, "B": 2, "C": 6}

    # 1. Rename only -- no "items" key at all.
    assert (
        client.patch(f"/api/bom-lists/{lid}", json={"name": "Renamed"}, headers=auth).status_code
        == 200
    )
    assert quantities() == {"A": 1, "B": 2, "C": 6}

    # 2. Resend the same items -- quantities survive the clear-and-rebuild.
    assert (
        client.patch(f"/api/bom-lists/{lid}", json={"items": payload}, headers=auth).status_code
        == 200
    )
    assert quantities() == {"A": 1, "B": 2, "C": 6}


def test_patch_authz_non_owner_403(client, auth):
    pid = _project(client, auth)
    i1 = _inventory("X")
    lid = client.post(
        "/api/bom-lists",
        json={"name": "Mine", "projectId": pid, "items": [{"inventoryId": i1}]},
        headers=auth,
    ).get_json()["id"]

    member = _register(client, "member@x.com")
    res = client.patch(f"/api/bom-lists/{lid}", json={"name": "Hijack"}, headers=member)
    assert res.status_code == 403


def test_delete_authz_and_cascade(client, auth):
    pid = _project(client, auth)
    i1, i2 = (_inventory(n) for n in ("A", "B"))
    lid = client.post(
        "/api/bom-lists",
        json={
            "name": "Doomed",
            "projectId": pid,
            "items": [{"inventoryId": i1}, {"inventoryId": i2}],
        },
        headers=auth,
    ).get_json()["id"]

    member = _register(client, "member2@x.com")
    assert client.delete(f"/api/bom-lists/{lid}", headers=member).status_code == 403
    assert client.delete(f"/api/bom-lists/{lid}", headers=auth).status_code == 204
    # Cascade: list-item rows are gone
    assert Session.query(BomListItem).filter_by(list_id=lid).count() == 0


def test_catalogue_entry_delete_cascades_into_list_items(client, auth):
    pid = _project(client, auth)
    i1, i2 = (_inventory(n) for n in ("A", "B"))
    lid = client.post(
        "/api/bom-lists",
        json={"name": "L", "projectId": pid, "items": [{"inventoryId": i1}, {"inventoryId": i2}]},
        headers=auth,
    ).get_json()["id"]

    # Retiring a catalogue entry cascades its list-item away (no API for this;
    # the catalogue is SQL-managed).
    Session.delete(Session.get(Inventory, i1))
    Session.commit()

    detail = client.get(f"/api/bom-lists/{lid}", headers=auth).get_json()
    assert detail["itemCount"] == 1
    assert {it["deviceName"] for it in detail["items"]} == {"B"}


def test_create_with_unknown_inventory_id_422(client, auth):
    pid = _project(client, auth)
    res = client.post(
        "/api/bom-lists",
        json={"name": "Bogus", "projectId": pid, "items": [{"inventoryId": 999999}]},
        headers=auth,
    )
    assert res.status_code == 422


def test_create_with_malformed_items_422(client, auth):
    pid = _project(client, auth)
    for bad in ([{"quantity": 2}], [5], "nope"):
        res = client.post(
            "/api/bom-lists",
            json={"name": "Bogus", "projectId": pid, "items": bad},
            headers=auth,
        )
        assert res.status_code == 422, bad


def test_create_with_unknown_project_422(client, auth):
    res = client.post(
        "/api/bom-lists",
        json={"name": "Bogus", "projectId": 999999, "items": []},
        headers=auth,
    )
    assert res.status_code == 422


def test_endpoints_require_auth(client):
    assert client.get("/api/bom-lists").status_code == 401
    assert client.get("/api/bom-lists/1").status_code == 401
    assert client.post("/api/bom-lists", json={}).status_code == 401
