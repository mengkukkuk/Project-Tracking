"""Supplier directory endpoint: read-only reference data (like /api/lookups)."""
from app.extensions import Session
from app.models import Supplier


def _supplier(**over):
    row = Supplier(**over)
    Session.add(row)
    Session.commit()
    return row.id


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
