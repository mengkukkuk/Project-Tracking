"""Inventory catalogue endpoints: read shape + capability-gated writes.

The `auth` fixture is the first registered user, so it is `admin`. Additional
users registered afterwards are `member`. Create is member-level
(`inventory.create`); update/delete are elevated-only (`inventory.update` /
`inventory.delete`) — the catalogue has no owner column, so there is no
ownership scope to narrow, only the capability gate.
"""
from app.extensions import Session
from app.models import Inventory, LookupType, LookupValue


def _inventory(name, **over):
    row = Inventory(device_name=name, **over)
    Session.add(row)
    Session.commit()
    return row.id


def _register(client, email, name="Member"):
    res = client.post(
        "/api/auth/register",
        json={"name": name, "email": email, "password": "secret123"},
    )
    assert res.status_code == 201, res.get_json()
    return {"Authorization": f"Bearer {res.get_json()['token']}"}


def test_list_inventory_shape_and_order(client, auth):
    _inventory("Zebra device", unit_price=200, supplier="IIS", unit="pcs")
    _inventory("Alpha device", unit_price=100)

    body = client.get("/api/inventory", headers=auth).get_json()
    names = [r["deviceName"] for r in body["items"]]
    assert names == ["Alpha device", "Zebra device"]  # ordered by device_name

    zebra = next(r for r in body["items"] if r["deviceName"] == "Zebra device")
    assert zebra["unitPrice"] == 200
    assert zebra["supplier"] == "IIS"
    assert zebra["unit"] == "pcs"
    # A catalogue entry is project-independent and quantity-free by design.
    for absent in ("projectId", "projectName", "position", "quantity", "totalPrice"):
        assert absent not in zebra


def test_unclassified_entry_has_null_taxonomy_labels(client, auth):
    # Most live catalogue rows are unclassified; they must serialize cleanly
    # rather than fall back to free text (there is no free-text column here).
    _inventory("Bare model number")
    row = client.get("/api/inventory", headers=auth).get_json()["items"][0]
    assert row["category"] is None
    assert row["categoryId"] is None
    assert row["type"] is None
    assert row["typeId"] is None


def test_classified_entry_resolves_taxonomy_labels(client, auth):
    t = LookupType(code="CAMERA", name="Camera", description="Camera")
    Session.add(t)
    Session.flush()
    v = LookupValue(lookup_type_id=t.id, code="INDUSTRIAL_CAM", display_name="Industrial camera")
    Session.add(v)
    Session.commit()
    _inventory("Industrial Camera : 5MP", category_id=t.id, type_id=v.id)

    row = client.get("/api/inventory", headers=auth).get_json()["items"][0]
    assert row["category"] == "Camera"
    assert row["type"] == "Industrial camera"


def test_inventory_requires_auth(client):
    assert client.get("/api/inventory").status_code == 401
    assert client.post("/api/inventory", json={"deviceName": "X"}).status_code == 401


# --- create (member-level capability) ----------------------------------------

def test_member_can_create_entry(client, auth):
    member = _register(client, "m@x.com")
    res = client.post(
        "/api/inventory",
        json={"deviceName": "Sensor X", "unitPrice": 900, "supplier": "IIS", "unit": "pcs"},
        headers=member,
    )
    assert res.status_code == 201, res.get_json()
    body = res.get_json()
    assert body["deviceName"] == "Sensor X"
    assert body["unitPrice"] == 900
    # Catalogue shape: project-independent, quantity-free.
    for absent in ("projectId", "projectName", "position", "quantity", "totalPrice"):
        assert absent not in body

    names = [r["deviceName"] for r in client.get("/api/inventory", headers=auth).get_json()["items"]]
    assert "Sensor X" in names


def test_create_requires_device_name(client, auth):
    assert client.post("/api/inventory", json={}, headers=auth).status_code == 422
    assert (
        client.post("/api/inventory", json={"deviceName": "   "}, headers=auth).status_code
        == 422
    )


def test_create_validates_numeric_fields(client, auth):
    bad = client.post(
        "/api/inventory", json={"deviceName": "X", "unitPrice": "abc"}, headers=auth
    )
    assert bad.status_code == 422
    negative = client.post(
        "/api/inventory", json={"deviceName": "X", "unitPrice": -1}, headers=auth
    )
    assert negative.status_code == 422


def test_create_ignores_unknown_fields(client, auth):
    res = client.post(
        "/api/inventory",
        json={"deviceName": "X", "quantity": 5, "projectId": 1},
        headers=auth,
    )
    assert res.status_code == 201, res.get_json()
    assert "quantity" not in res.get_json()


# --- update / delete (elevated-only capability) --------------------------------

def test_member_cannot_update_or_delete(client, auth):
    member = _register(client, "m@x.com")
    iid = _inventory("Locked device", unit_price=100)
    assert (
        client.patch(f"/api/inventory/{iid}", json={"unitPrice": 1}, headers=member).status_code
        == 403
    )
    assert client.delete(f"/api/inventory/{iid}", headers=member).status_code == 403


def test_admin_partial_patch(client, auth):
    iid = _inventory("Camera VC-200", unit_price=1500, supplier="IIS")
    res = client.patch(f"/api/inventory/{iid}", json={"unitPrice": 1750}, headers=auth)
    assert res.status_code == 200, res.get_json()
    body = res.get_json()
    assert body["unitPrice"] == 1750
    assert body["supplier"] == "IIS"          # untouched fields survive
    assert body["deviceName"] == "Camera VC-200"

    # deviceName may be omitted on PATCH but never blanked.
    assert (
        client.patch(f"/api/inventory/{iid}", json={"deviceName": ""}, headers=auth).status_code
        == 422
    )
    assert client.patch("/api/inventory/99999", json={"unitPrice": 1}, headers=auth).status_code == 404


def test_admin_can_delete(client, auth):
    iid = _inventory("Doomed device")
    assert client.delete(f"/api/inventory/{iid}", headers=auth).status_code == 204
    names = [r["deviceName"] for r in client.get("/api/inventory", headers=auth).get_json()["items"]]
    assert "Doomed device" not in names
    assert client.delete("/api/inventory/99999", headers=auth).status_code == 404


def test_delete_cascades_out_of_saved_lists(client, auth):
    # API-level counterpart of the ORM cascade test in test_bom_lists.py:
    # deleting a catalogue entry silently shrinks lists that reference it.
    pid = client.post(
        "/api/projects", json={"name": "Host", "status": "Pre-Sale"}, headers=auth
    ).get_json()["id"]
    keep = _inventory("Keeper", unit_price=100)
    doomed = _inventory("Doomed", unit_price=200)
    lid = client.post(
        "/api/bom-lists",
        json={
            "name": "Cascade check",
            "projectId": pid,
            "items": [{"inventoryId": keep, "quantity": 1}, {"inventoryId": doomed, "quantity": 2}],
        },
        headers=auth,
    ).get_json()["id"]

    assert client.delete(f"/api/inventory/{doomed}", headers=auth).status_code == 204
    items = client.get(f"/api/bom-lists/{lid}", headers=auth).get_json()["items"]
    assert [it["deviceName"] for it in items] == ["Keeper"]
