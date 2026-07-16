"""Supplier directory endpoint: read is open to any authenticated user;
create/update are admin-only capability gates (``suppliers.create`` /
``suppliers.update``) — the supplier profile has no owner column, so there is
no ownership scope to narrow, only the capability gate. The `auth` fixture is
the first registered user, so it is `admin`; additional users registered
afterwards are `member`.
"""
from app.extensions import Session
from app.models import Supplier


def _supplier(**over):
    row = Supplier(**over)
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


def test_list_suppliers_requires_auth(client):
    assert client.get("/api/suppliers").status_code == 401


def test_list_suppliers_shape_and_order(client, auth):
    _supplier(
        sup_name="บริษัท คีย์เอ็นซ์ (ไทยแลนด์) จำกัด",
        sup_code="KEYENCE",
        description="FA sensor\nCode-reader",
        address="2034/140-143 อาคารอิตัลไทย",
        telephone="02-078-1090",
        email="info@keyence.co.th",
        website="https://www.keyence.co.th/",
        tax_id="0105541007151",
    )
    _supplier(sup_name="Balluff", sup_code="BALLUFF")

    body = client.get("/api/suppliers", headers=auth).get_json()
    names = [r["name"] for r in body["items"]]
    assert names == sorted(names)  # ordered by sup_name

    key = next(r for r in body["items"] if r["code"] == "KEYENCE")
    assert key["name"].startswith("บริษัท")
    assert key["telephone"] == "02-078-1090"
    assert key["email"] == "info@keyence.co.th"
    assert key["website"] == "https://www.keyence.co.th/"
    assert key["taxId"] == "0105541007151"
    # Unset contact fields serialize as None, not missing keys.
    assert key["mobile"] is None
    assert key["lineAcc"] is None


# --- create / update (admin-only capability) ----------------------------------

def test_member_cannot_create_or_update(client, auth):
    member = _register(client, "m@x.com")
    sid = _supplier(sup_name="Locked supplier")
    assert (
        client.post("/api/suppliers", json={"name": "New Co"}, headers=member).status_code
        == 403
    )
    assert (
        client.patch(f"/api/suppliers/{sid}", json={"name": "X"}, headers=member).status_code
        == 403
    )


def test_admin_create_name_only_required(client, auth):
    res = client.post("/api/suppliers", json={"name": "Balluff"}, headers=auth)
    assert res.status_code == 201, res.get_json()
    body = res.get_json()
    assert body["name"] == "Balluff"
    assert body["code"] is None

    assert client.post("/api/suppliers", json={}, headers=auth).status_code == 422
    assert client.post("/api/suppliers", json={"name": "   "}, headers=auth).status_code == 422


def test_admin_partial_update(client, auth):
    sid = _supplier(sup_name="Keyence", sup_code="KEYENCE", email="info@keyence.co.th")
    res = client.patch(f"/api/suppliers/{sid}", json={"email": "new@keyence.co.th"}, headers=auth)
    assert res.status_code == 200, res.get_json()
    body = res.get_json()
    assert body["email"] == "new@keyence.co.th"
    assert body["name"] == "Keyence"        # untouched fields survive
    assert body["code"] == "KEYENCE"

    # name may be omitted on PATCH but never blanked.
    assert (
        client.patch(f"/api/suppliers/{sid}", json={"name": ""}, headers=auth).status_code == 422
    )
    assert client.patch("/api/suppliers/99999", json={"name": "X"}, headers=auth).status_code == 404
