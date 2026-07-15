"""Read-only inventory catalogue endpoint."""
from app.extensions import Session
from app.models import Inventory, LookupType, LookupValue


def _inventory(name, **over):
    row = Inventory(device_name=name, **over)
    Session.add(row)
    Session.commit()
    return row.id


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


def test_inventory_is_read_only(client, auth):
    # No write surface: the catalogue is managed via SQL/seed.
    assert client.post("/api/inventory", json={"deviceName": "X"}, headers=auth).status_code == 405
