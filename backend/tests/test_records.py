"""Per-project records CRUD + ptemplate->ptrack bulk insert."""
from app.extensions import Session
from app.models import ProcessTag, PTemplate


def _project(client, auth, **over):
    body = {"name": "Host", "status": "Pre-Sale", **over}
    return client.post("/api/projects", json=body, headers=auth).get_json()["id"]


def _register(client, email, name="Member"):
    res = client.post(
        "/api/auth/register",
        json={"name": name, "email": email, "password": "secret123"},
    )
    return {"Authorization": f"Bearer {res.get_json()['token']}"}


def test_ptemplate_bulk_inserts_into_ptrack(client, auth):
    # The process *name* lives in process_tags; ptemplate links by processid.
    Session.add_all([
        ProcessTag(processid=1, process="Pre-Sale"),
        ProcessTag(processid=2, process="Award"),
    ])
    Session.commit()

    # Seed two template rows (the registering user is admin).
    for processid, task in [(1, "Survey"), (2, "Sign contract")]:
        res = client.post(
            "/api/ptemplate",
            json={"task": task, "processId": processid},
            headers=auth,
        )
        assert res.status_code == 201, res.get_json()

    pid = _project(client, auth, pm="นายเอ")

    rows = client.get(
        f"/api/projects/{pid}/records/ptrack", headers=auth
    ).get_json()["items"]
    assert len(rows) == 2
    # process is resolved from process_tags via the template's processid.
    assert {r["process"] for r in rows} == {"Pre-Sale", "Award"}
    assert all(r["pm"] == "นายเอ" for r in rows)
    assert all(r["checked"] is False for r in rows)


def test_record_crud_bom(client, auth):
    pid = _project(client, auth)
    res = client.post(
        f"/api/projects/{pid}/records/bom",
        json={
            "category": "Sensor",
            "deviceName": "Camera X",
            "quantity": 2,
            "unitPrice": 5000,
            "totalPrice": 10000,
            "dateApprove": "2026-06-15",
        },
        headers=auth,
    )
    assert res.status_code == 201, res.get_json()
    rec = res.get_json()
    assert rec["deviceName"] == "Camera X"
    assert rec["unitPrice"] == 5000
    assert rec["dateApprove"] == "2026-06-15"
    rid = rec["id"]

    res = client.patch(
        f"/api/records/bom/{rid}", json={"quantity": 3}, headers=auth
    )
    assert res.get_json()["quantity"] == 3

    items = client.get(
        f"/api/projects/{pid}/records/bom", headers=auth
    ).get_json()["items"]
    assert len(items) == 1

    assert client.delete(f"/api/records/bom/{rid}", headers=auth).status_code == 204


def test_list_all_bom_across_projects(client, auth):
    # Two projects, each with one BOM row.
    p1 = _project(client, auth, name="Alpha")
    p2 = _project(client, auth, name="Beta")
    client.post(
        f"/api/projects/{p1}/records/bom",
        json={"deviceName": "Camera X", "quantity": 1},
        headers=auth,
    )
    client.post(
        f"/api/projects/{p2}/records/bom",
        json={"deviceName": "PLC Y", "quantity": 2},
        headers=auth,
    )

    items = client.get("/api/bom/all", headers=auth).get_json()["items"]
    assert len(items) == 2
    # Rows from both projects, each enriched with its project name.
    by_device = {it["deviceName"]: it for it in items}
    assert by_device["Camera X"]["projectName"] == "Alpha"
    assert by_device["Camera X"]["projectId"] == p1
    assert by_device["PLC Y"]["projectName"] == "Beta"
    assert by_device["PLC Y"]["projectId"] == p2


def test_list_all_bom_requires_auth(client):
    assert client.get("/api/bom/all").status_code == 401


def test_record_crud_mom(client, auth):
    pid = _project(client, auth)
    res = client.post(
        f"/api/projects/{pid}/records/mom",
        json={"topic": "Kickoff", "participant": "A,B", "date": "2026-06-15"},
        headers=auth,
    )
    assert res.status_code == 201
    assert res.get_json()["topic"] == "Kickoff"


def test_unknown_resource_404(client, auth):
    pid = _project(client, auth)
    res = client.get(f"/api/projects/{pid}/records/nope", headers=auth)
    assert res.status_code == 404


def test_records_require_auth(client):
    res = client.get("/api/projects/1/records/bom")
    assert res.status_code == 401


def test_project_dict_has_process_counts(client, auth):
    Session.add_all([
        ProcessTag(processid=1, process="Pre-Sale"),
        ProcessTag(processid=2, process="Award"),
    ])
    Session.add_all([
        PTemplate(processid=1, task="Survey"),
        PTemplate(processid=2, task="Sign contract"),
    ])
    Session.commit()

    pid = _project(client, auth)
    proj = client.get(f"/api/projects/{pid}", headers=auth).get_json()
    assert proj["processCount"] == 2
    assert proj["processDone"] == 0

    rows = client.get(
        f"/api/projects/{pid}/records/ptrack", headers=auth
    ).get_json()["items"]
    client.patch(
        f"/api/records/ptrack/{rows[0]['id']}", json={"checked": True}, headers=auth
    )
    proj = client.get(f"/api/projects/{pid}", headers=auth).get_json()
    assert proj["processDone"] == 1


def test_generate_ptrack_for_empty_project(client, auth):
    # Created before any template exists -> empty ptrack (simulates old project).
    pid = _project(client, auth)
    assert client.get(f"/api/projects/{pid}", headers=auth).get_json()["processCount"] == 0

    Session.add(ProcessTag(processid=1, process="Pre-Sale"))
    Session.add_all([
        PTemplate(processid=1, task="Survey"),
        PTemplate(processid=1, task="Draft"),
    ])
    Session.commit()

    res = client.post(f"/api/projects/{pid}/ptrack/generate", headers=auth)
    assert res.status_code == 200, res.get_json()
    assert res.get_json()["processCount"] == 2

    rows = client.get(
        f"/api/projects/{pid}/records/ptrack", headers=auth
    ).get_json()["items"]
    assert {r["process"] for r in rows} == {"Pre-Sale"}


def test_generate_ptrack_idempotent(client, auth):
    Session.add(PTemplate(processid=1, task="Survey"))
    Session.commit()
    pid = _project(client, auth)  # create-time seed already populated 1 row
    res = client.post(f"/api/projects/{pid}/ptrack/generate", headers=auth)
    assert res.status_code == 409


def test_generate_ptrack_authz(client, auth):
    pid = _project(client, auth)  # owner = admin (the auth fixture user)
    member = _register(client, "member@x.com")
    res = client.post(f"/api/projects/{pid}/ptrack/generate", headers=member)
    assert res.status_code == 403
