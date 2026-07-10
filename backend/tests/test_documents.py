"""Per-project PDF document uploads (docstore)."""
import io
import os

from app import create_app
from app.config import TestConfig
from app.extensions import Session
from app.models import ProjectDocument


def _project(client, auth, **over):
    body = {"name": "Host", "status": "Pre-Sale", **over}
    return client.post("/api/projects", json=body, headers=auth).get_json()["id"]


def _register(client, email, name="Member"):
    res = client.post(
        "/api/auth/register",
        json={"name": name, "email": email, "password": "secret123"},
    )
    return {"Authorization": f"Bearer {res.get_json()['token']}"}


def _pdf(name="q.pdf", body=b"%PDF-1.4\nfake pdf body"):
    return (io.BytesIO(body), name)


def _upload(client, auth, pid, doc_type, files):
    return client.post(
        f"/api/projects/{pid}/documents/{doc_type}",
        data={"files": files},
        content_type="multipart/form-data",
        headers=auth,
    )


def test_upload_and_list(client, auth):
    pid = _project(client, auth)
    res = _upload(client, auth, pid, "quotation", [_pdf("a.pdf"), _pdf("b.pdf")])
    assert res.status_code == 201, res.get_json()
    items = res.get_json()["items"]
    assert len(items) == 2
    assert {i["name"] for i in items} == {"a.pdf", "b.pdf"}
    assert all(i["docType"] == "quotation" for i in items)
    assert all(i["projectId"] == pid for i in items)
    assert all(i["size"] > 0 for i in items)
    assert all(i["user"]["name"] == "Tester" for i in items)

    listed = client.get(f"/api/projects/{pid}/documents", headers=auth).get_json()
    assert len(listed["items"]) == 2

    # ?type= filter
    only = client.get(
        f"/api/projects/{pid}/documents?type=tds", headers=auth
    ).get_json()
    assert only["items"] == []

    # Files land on disk under <docstore>/<pid>/quotation with uuid names.
    folder = os.path.join(TestConfig.DOCSTORE_DIR, str(pid), "quotation")
    assert len(os.listdir(folder)) == 2
    assert all(f.endswith(".pdf") for f in os.listdir(folder))
    assert "a.pdf" not in os.listdir(folder)


def test_upload_thai_filename_preserved(client, auth):
    pid = _project(client, auth)
    res = _upload(client, auth, pid, "quotation", [_pdf("ใบเสนอราคา.pdf")])
    assert res.status_code == 201, res.get_json()
    assert res.get_json()["items"][0]["name"] == "ใบเสนอราคา.pdf"


def test_upload_rejects_non_pdf_extension(client, auth):
    pid = _project(client, auth)
    res = _upload(client, auth, pid, "result", [_pdf("notes.txt")])
    assert res.status_code == 422
    assert res.get_json()["error"]["type"] == "validation"


def test_upload_rejects_fake_pdf_all_or_nothing(client, auth):
    pid = _project(client, auth)
    # One good file + one with a .pdf name but wrong magic bytes: nothing persists.
    res = _upload(
        client, auth, pid, "tds", [_pdf("ok.pdf"), _pdf("fake.pdf", b"not a pdf")]
    )
    assert res.status_code == 422
    listed = client.get(f"/api/projects/{pid}/documents", headers=auth).get_json()
    assert listed["items"] == []
    folder = os.path.join(TestConfig.DOCSTORE_DIR, str(pid), "tds")
    assert not os.path.isdir(folder) or os.listdir(folder) == []


def test_upload_unknown_doc_type_404(client, auth):
    pid = _project(client, auth)
    res = _upload(client, auth, pid, "invoice", [_pdf()])
    assert res.status_code == 404


def test_upload_missing_project_404(client, auth):
    res = _upload(client, auth, 999, "quotation", [_pdf()])
    assert res.status_code == 404


def test_upload_no_files_422(client, auth):
    pid = _project(client, auth)
    res = client.post(
        f"/api/projects/{pid}/documents/quotation",
        data={},
        content_type="multipart/form-data",
        headers=auth,
    )
    assert res.status_code == 422


def test_documents_require_auth(client, auth):
    pid = _project(client, auth)
    assert client.get(f"/api/projects/{pid}/documents").status_code == 401
    res = client.post(
        f"/api/projects/{pid}/documents/quotation",
        data={"files": [_pdf()]},
        content_type="multipart/form-data",
    )
    assert res.status_code == 401


def test_download_roundtrip(client, auth):
    pid = _project(client, auth)
    body = b"%PDF-1.7\nreal enough"
    doc = _upload(client, auth, pid, "result", [_pdf("report.pdf", body)]).get_json()[
        "items"
    ][0]

    res = client.get(f"/api/documents/{doc['id']}/download", headers=auth)
    assert res.status_code == 200
    assert res.data == body
    assert "attachment" in res.headers["Content-Disposition"]
    assert "report.pdf" in res.headers["Content-Disposition"]

    assert client.get("/api/documents/999/download", headers=auth).status_code == 404


def test_delete_authz_and_file_removal(client, auth):
    pid = _project(client, auth)
    doc = _upload(client, auth, pid, "quotation", [_pdf()]).get_json()["items"][0]
    path = os.path.join(
        TestConfig.DOCSTORE_DIR, str(pid), "quotation", os.listdir(
            os.path.join(TestConfig.DOCSTORE_DIR, str(pid), "quotation")
        )[0],
    )
    assert os.path.isfile(path)

    # A plain member who doesn't own the project may not delete.
    member = _register(client, "m@x.com")
    assert client.delete(f"/api/documents/{doc['id']}", headers=member).status_code == 403

    # The owner (admin fixture) may; the row and the disk file both go away.
    assert client.delete(f"/api/documents/{doc['id']}", headers=auth).status_code == 204
    listed = client.get(f"/api/projects/{pid}/documents", headers=auth).get_json()
    assert listed["items"] == []
    assert not os.path.isfile(path)

    assert client.delete(f"/api/documents/{doc['id']}", headers=auth).status_code == 404


def test_project_delete_removes_docstore(client, auth):
    pid = _project(client, auth)
    _upload(client, auth, pid, "quotation", [_pdf()])
    _upload(client, auth, pid, "result", [_pdf("r.pdf")])
    assert os.path.isdir(os.path.join(TestConfig.DOCSTORE_DIR, str(pid)))

    assert client.delete(f"/api/projects/{pid}", headers=auth).status_code == 204
    assert not os.path.isdir(os.path.join(TestConfig.DOCSTORE_DIR, str(pid)))
    assert Session.query(ProjectDocument).count() == 0


def test_upload_too_large_413(client, auth):
    # Rebuild the app with a tiny cap; Werkzeug rejects the body before the view
    # runs and errors.py turns it into the standard envelope.
    class SmallConfig(TestConfig):
        MAX_CONTENT_LENGTH = 1024

    small = create_app(SmallConfig).test_client()
    res = small.post(
        "/api/auth/register",
        json={"name": "S", "email": "s@x.com", "password": "secret123"},
    )
    headers = {"Authorization": f"Bearer {res.get_json()['token']}"}
    pid = small.post(
        "/api/projects", json={"name": "Big"}, headers=headers
    ).get_json()["id"]

    res = small.post(
        f"/api/projects/{pid}/documents/quotation",
        data={"files": [_pdf("big.pdf", b"%PDF-1.4\n" + b"x" * 4096)]},
        content_type="multipart/form-data",
        headers=headers,
    )
    assert res.status_code == 413
    assert res.get_json()["error"]["code"] == 413
