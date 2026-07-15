"""Inventory catalogue image gallery (imagestore).

Authz here is deliberately member-level for BOTH upload and delete
(`inventory.create`), unlike documents.py's owner-or-admin delete — the
inventory catalogue has no owner column. The `auth` fixture is the first
registered user (admin); users registered afterwards are members.
"""
import io
import os

from app.config import TestConfig
from app.extensions import Session
from app.models import Inventory, InventoryImage

# Minimal but magic-valid image bodies (>= 12 bytes; the view reads a 12-byte
# head). Byte 8..11 carry the WEBP tag.
PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\x00rest"
JPG = b"\xff\xd8\xff" + b"\x00" * 20
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 more"
GIF = b"GIF89a" + b"\x00" * 12


def _inventory(name="Widget", **over):
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


def _img(name="a.png", body=PNG):
    return (io.BytesIO(body), name)


def _upload(client, headers, iid, files):
    return client.post(
        f"/api/inventory/{iid}/images",
        data={"files": files},
        content_type="multipart/form-data",
        headers=headers,
    )


def test_upload_and_list(client, auth):
    iid = _inventory()
    res = _upload(client, auth, iid, [_img("a.png"), _img("b.jpg", JPG)])
    assert res.status_code == 201, res.get_json()
    items = res.get_json()["items"]
    assert len(items) == 2
    assert {i["name"] for i in items} == {"a.png", "b.jpg"}
    assert all(i["inventoryId"] == iid for i in items)
    assert all(i["size"] > 0 for i in items)
    assert all(i["user"]["name"] == "Tester" for i in items)

    listed = client.get(f"/api/inventory/{iid}/images", headers=auth).get_json()
    assert len(listed["items"]) == 2

    # Files land under <imagestore>/<iid>/ with server-generated uuid names.
    folder = os.path.join(TestConfig.IMAGESTORE_DIR, str(iid))
    assert len(os.listdir(folder)) == 2
    assert "a.png" not in os.listdir(folder)


def test_upload_thai_filename_preserved(client, auth):
    iid = _inventory()
    res = _upload(client, auth, iid, [_img("รูปสินค้า.png")])
    assert res.status_code == 201, res.get_json()
    assert res.get_json()["items"][0]["name"] == "รูปสินค้า.png"


def test_upload_all_formats_mime(client, auth):
    iid = _inventory()
    res = _upload(
        client,
        auth,
        iid,
        [_img("a.png", PNG), _img("b.jpg", JPG), _img("c.webp", WEBP), _img("d.gif", GIF)],
    )
    assert res.status_code == 201, res.get_json()
    by_name = {i["name"]: i["mimeType"] for i in res.get_json()["items"]}
    assert by_name["a.png"] == "image/png"
    assert by_name["b.jpg"] == "image/jpeg"
    assert by_name["c.webp"] == "image/webp"
    assert by_name["d.gif"] == "image/gif"


def test_upload_rejects_bad_extension(client, auth):
    iid = _inventory()
    res = _upload(client, auth, iid, [_img("notes.txt", PNG)])
    assert res.status_code == 422
    assert res.get_json()["error"]["type"] == "validation"


def test_upload_fake_magic_all_or_nothing(client, auth):
    iid = _inventory()
    # One valid + one with a .png name but wrong magic bytes: nothing persists.
    res = _upload(client, auth, iid, [_img("ok.png", PNG), _img("fake.png", b"not an image")])
    assert res.status_code == 422
    assert client.get(f"/api/inventory/{iid}/images", headers=auth).get_json()["items"] == []
    folder = os.path.join(TestConfig.IMAGESTORE_DIR, str(iid))
    assert not os.path.isdir(folder) or os.listdir(folder) == []


def test_upload_no_files_422(client, auth):
    iid = _inventory()
    res = client.post(
        f"/api/inventory/{iid}/images",
        data={},
        content_type="multipart/form-data",
        headers=auth,
    )
    assert res.status_code == 422


def test_upload_missing_item_404(client, auth):
    res = _upload(client, auth, 9999, [_img()])
    assert res.status_code == 404


def test_images_require_auth(client, auth):
    iid = _inventory()
    assert client.get(f"/api/inventory/{iid}/images").status_code == 401
    res = client.post(
        f"/api/inventory/{iid}/images",
        data={"files": [_img()]},
        content_type="multipart/form-data",
    )
    assert res.status_code == 401


def test_blob_roundtrip_inline(client, auth):
    iid = _inventory()
    img = _upload(client, auth, iid, [_img("a.png", PNG)]).get_json()["items"][0]
    res = client.get(f"/api/inventory-images/{img['id']}", headers=auth)
    assert res.status_code == 200
    assert res.data == PNG
    assert res.headers["Content-Type"] == "image/png"
    # Inline (displayed), not an attachment.
    assert "attachment" not in res.headers.get("Content-Disposition", "")
    assert client.get("/api/inventory-images/9999", headers=auth).status_code == 404


def test_member_can_upload_and_delete(client, auth):
    # The key member-level assertion: a plain member (inventory.create only, no
    # inventory.update/delete) may both upload AND delete images.
    member = _register(client, "m@x.com")
    iid = _inventory()
    up = _upload(client, member, iid, [_img("a.png", PNG)])
    assert up.status_code == 201, up.get_json()
    img_id = up.get_json()["items"][0]["id"]
    assert client.delete(f"/api/inventory-images/{img_id}", headers=member).status_code == 204


def test_delete_removes_row_and_file(client, auth):
    iid = _inventory()
    img = _upload(client, auth, iid, [_img("a.png", PNG)]).get_json()["items"][0]
    folder = os.path.join(TestConfig.IMAGESTORE_DIR, str(iid))
    path = os.path.join(folder, os.listdir(folder)[0])
    assert os.path.isfile(path)

    assert client.delete(f"/api/inventory-images/{img['id']}", headers=auth).status_code == 204
    assert client.get(f"/api/inventory/{iid}/images", headers=auth).get_json()["items"] == []
    assert not os.path.isfile(path)
    assert client.delete(f"/api/inventory-images/{img['id']}", headers=auth).status_code == 404


def test_inventory_delete_sweeps_imagestore(client, auth):
    # Deleting the catalogue entry (admin-only) cascades the image rows and
    # sweeps the whole imagestore/<iid>/ folder off disk.
    iid = _inventory()
    _upload(client, auth, iid, [_img("a.png", PNG), _img("b.jpg", JPG)])
    folder = os.path.join(TestConfig.IMAGESTORE_DIR, str(iid))
    assert os.path.isdir(folder)

    assert client.delete(f"/api/inventory/{iid}", headers=auth).status_code == 204
    assert not os.path.isdir(folder)
    assert Session.query(InventoryImage).count() == 0
