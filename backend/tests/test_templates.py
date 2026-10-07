"""Process templates: template_no-scoped seeding, date chain, and authoring API."""
from datetime import date, timedelta

from app.extensions import Session
from app.models import ProcessTag, Project, PTemplate


def _register(client, email, name="Member"):
    res = client.post(
        "/api/auth/register",
        json={"name": name, "email": email, "password": "secret123"},
    )
    assert res.status_code == 201, res.get_json()
    return {"Authorization": f"Bearer {res.get_json()['token']}"}


def _two_templates():
    """Template 1: A(3d) -> B(4d). Template 2: X(10d). processid 1 collides."""
    Session.add_all([
        ProcessTag(template_no=1, processid=1, process="A", day_range=3),
        ProcessTag(template_no=1, processid=2, process="B", day_range=4),
        ProcessTag(template_no=2, processid=1, process="X", day_range=10),
        PTemplate(template_no=1, processid=1, task="a1"),
        PTemplate(template_no=1, processid=1, task="a2"),
        PTemplate(template_no=1, processid=2, task="b1"),
        PTemplate(template_no=2, processid=1, task="x1"),
    ])
    Session.commit()


def _project(client, auth, **over):
    res = client.post("/api/projects", json={"name": "P", **over}, headers=auth)
    assert res.status_code == 201, res.get_json()
    return res.get_json()


def _ptrack(client, auth, pid):
    return client.get(f"/api/projects/{pid}/records/ptrack", headers=auth).get_json()["items"]


# ── seeding ───────────────────────────────────────────────────────────────────


def test_default_template_is_one(client, auth):
    _two_templates()
    p = _project(client, auth)
    assert p["templateNo"] == 1
    rows = _ptrack(client, auth, p["id"])
    assert sorted(r["task"] for r in rows) == ["a1", "a2", "b1"]
    assert {r["process"] for r in rows} == {"A", "B"}


def test_chosen_template_seeds_only_its_rows(client, auth):
    _two_templates()
    p = _project(client, auth, templateNo=2)
    assert p["templateNo"] == 2
    rows = _ptrack(client, auth, p["id"])
    assert [(r["task"], r["process"]) for r in rows] == [("x1", "X")]


def test_unknown_template_is_422(client, auth):
    _two_templates()
    res = client.post(
        "/api/projects", json={"name": "P", "templateNo": 9}, headers=auth
    )
    assert res.status_code == 422


def test_patch_ignores_template_no(client, auth):
    _two_templates()
    p = _project(client, auth, templateNo=2)
    res = client.patch(f"/api/projects/{p['id']}", json={"templateNo": 1}, headers=auth)
    assert res.status_code == 200
    assert res.get_json()["templateNo"] == 2


def test_generate_uses_project_template(client, auth):
    p = _project(client, auth, name="Old")  # no templates yet -> empty checklist
    assert p["processCount"] == 0
    _two_templates()
    proj = Session.get(Project, p["id"])
    proj.template_no = 2
    Session.commit()
    res = client.post(f"/api/projects/{p['id']}/ptrack/generate", headers=auth)
    assert res.status_code == 200
    assert [r["task"] for r in _ptrack(client, auth, p["id"])] == ["x1"]


# ── date chain isolation ──────────────────────────────────────────────────────


def test_day_range_and_dates_come_from_own_template(client, auth):
    _two_templates()
    start = date(2026, 1, 1)
    p1 = _project(client, auth, startDate=start.isoformat())
    p2 = _project(client, auth, startDate=start.isoformat(), templateNo=2)

    rows1 = {r["process"]: r for r in _ptrack(client, auth, p1["id"])}
    assert rows1["A"]["dayRange"] == 3 and rows1["A"]["cumulativeDays"] == 3
    assert rows1["B"]["dayRange"] == 4 and rows1["B"]["cumulativeDays"] == 7
    assert rows1["B"]["startDate"] == (start + timedelta(days=4)).isoformat()

    rows2 = _ptrack(client, auth, p2["id"])
    assert rows2[0]["process"] == "X"
    assert rows2[0]["dayRange"] == 10 and rows2[0]["cumulativeDays"] == 10
    assert rows2[0]["dueDate"] == (start + timedelta(days=10)).isoformat()


# ── read endpoints ────────────────────────────────────────────────────────────


def test_list_and_get_templates(client, auth):
    _two_templates()
    _project(client, auth, templateNo=2)
    member = _register(client, "m@x.com")

    items = client.get("/api/templates", headers=member).get_json()["items"]
    assert items == [
        {"templateNo": 1, "name": None, "processCount": 2, "taskCount": 3, "projectCount": 0},
        {"templateNo": 2, "name": None, "processCount": 1, "taskCount": 1, "projectCount": 1},
    ]

    t1 = client.get("/api/templates/1", headers=member).get_json()
    assert [p["process"] for p in t1["processes"]] == ["A", "B"]
    assert [t["task"] for t in t1["processes"][0]["tasks"]] == ["a1", "a2"]

    assert client.get("/api/templates/9", headers=member).status_code == 404


# ── authoring ─────────────────────────────────────────────────────────────────


def test_member_cannot_write_templates(client, auth):
    _two_templates()
    member = _register(client, "m@x.com")
    tid = Session.query(ProcessTag).first().id
    task_id = Session.query(PTemplate).first().id
    calls = [
        client.post("/api/templates", json={}, headers=member),
        client.post("/api/templates/1/processes", json={"process": "Z"}, headers=member),
        client.patch(f"/api/process-tags/{tid}", json={"process": "Z"}, headers=member),
        client.delete(f"/api/process-tags/{tid}", headers=member),
        client.post("/api/ptemplate", json={"task": "t", "processId": 1}, headers=member),
        client.patch(f"/api/ptemplate/{task_id}", json={"task": "t"}, headers=member),
        client.delete(f"/api/ptemplate/{task_id}", headers=member),
    ]
    assert [c.status_code for c in calls] == [403] * len(calls)


def test_create_blank_template_has_starter_process(client, auth):
    _two_templates()
    res = client.post("/api/templates", json={}, headers=auth)
    assert res.status_code == 201
    no = res.get_json()["templateNo"]
    assert no == 3
    t = client.get(f"/api/templates/{no}", headers=auth).get_json()
    assert len(t["processes"]) == 1 and t["processes"][0]["tasks"] == []
    # the new template is immediately selectable for a project
    assert _project(client, auth, templateNo=no)["templateNo"] == no


def test_clone_template_copies_rows(client, auth):
    _two_templates()
    no = client.post("/api/templates", json={"cloneFrom": 1}, headers=auth).get_json()["templateNo"]
    t = client.get(f"/api/templates/{no}", headers=auth).get_json()
    assert [p["process"] for p in t["processes"]] == ["A", "B"]
    assert [len(p["tasks"]) for p in t["processes"]] == [2, 1]
    # the source is untouched
    assert client.get("/api/templates/1", headers=auth).get_json()["processes"][0]["tasks"]
    assert client.post("/api/templates", json={"cloneFrom": 9}, headers=auth).status_code == 422


def test_process_crud_and_cascade(client, auth):
    _two_templates()
    created = client.post(
        "/api/templates/2/processes", json={"process": "Y", "dayRange": 5}, headers=auth
    )
    assert created.status_code == 201
    assert created.get_json()["processId"] == 2  # max + 1 within template 2

    pid = created.get_json()["id"]
    patched = client.patch(
        f"/api/process-tags/{pid}", json={"process": "Y2", "dayRange": 6}, headers=auth
    ).get_json()
    assert (patched["process"], patched["dayRange"]) == ("Y2", 6)

    task = client.post(
        "/api/ptemplate", json={"task": "y1", "processId": 2, "templateNo": 2}, headers=auth
    )
    assert task.status_code == 201
    assert client.delete(f"/api/process-tags/{pid}", headers=auth).status_code == 204
    assert Session.query(PTemplate).filter_by(task="y1").count() == 0
    # template 1's process 2 ("B") shares processid 2 and must be untouched
    assert Session.query(PTemplate).filter_by(task="b1").count() == 1


def test_cannot_delete_last_process(client, auth):
    _two_templates()
    only = Session.query(ProcessTag).filter_by(template_no=2).first().id
    res = client.delete(f"/api/process-tags/{only}", headers=auth)
    assert res.status_code == 409


def test_task_crud(client, auth):
    _two_templates()
    res = client.post(
        "/api/ptemplate",
        json={"task": "n", "processId": 1, "templateNo": 2, "results": "R", "undertaker": "U"},
        headers=auth,
    )
    assert res.status_code == 201
    body = res.get_json()
    assert (body["templateNo"], body["results"], body["undertaker"]) == (2, "R", "U")

    patched = client.patch(
        f"/api/ptemplate/{body['id']}", json={"task": "n2", "results": ""}, headers=auth
    ).get_json()
    assert patched["task"] == "n2" and patched["results"] is None and patched["undertaker"] == "U"

    # task must target an existing (template, process)
    bad = client.post(
        "/api/ptemplate", json={"task": "z", "processId": 7, "templateNo": 2}, headers=auth
    )
    assert bad.status_code == 422
    assert client.delete(f"/api/ptemplate/{body['id']}", headers=auth).status_code == 204


# ── names ─────────────────────────────────────────────────────────────────────


def test_template_names(client, auth):
    _two_templates()
    items = client.get("/api/templates", headers=auth).get_json()["items"]
    assert [t["name"] for t in items] == [None, None]

    res = client.patch("/api/templates/1", json={"name": "  Standard  "}, headers=auth)
    assert res.status_code == 200 and res.get_json()["name"] == "Standard"
    assert client.get("/api/templates/1", headers=auth).get_json()["name"] == "Standard"
    assert client.get("/api/templates", headers=auth).get_json()["items"][0]["name"] == "Standard"

    # rename, then clear with a blank name
    client.patch("/api/templates/1", json={"name": "Std 2"}, headers=auth)
    assert client.get("/api/templates/1", headers=auth).get_json()["name"] == "Std 2"
    client.patch("/api/templates/1", json={"name": ""}, headers=auth)
    assert client.get("/api/templates/1", headers=auth).get_json()["name"] is None

    assert client.patch("/api/templates/9", json={"name": "x"}, headers=auth).status_code == 404
    assert client.patch("/api/templates/1", json={}, headers=auth).status_code == 422
    member = _register(client, "m@x.com")
    assert client.patch("/api/templates/1", json={"name": "x"}, headers=member).status_code == 403


def test_create_template_with_name(client, auth):
    _two_templates()
    res = client.post("/api/templates", json={"name": "Retrofit"}, headers=auth)
    no = res.get_json()["templateNo"]
    assert client.get(f"/api/templates/{no}", headers=auth).get_json()["name"] == "Retrofit"


# ── changing a project's template ─────────────────────────────────────────────


def test_change_template_replaces_checklist_keeps_ticked(client, auth):
    _two_templates()
    Session.add(PTemplate(template_no=2, processid=1, task="a1"))  # shared with T1
    Session.commit()
    p = _project(client, auth)  # template 1: a1 a2 b1
    rows = {r["task"]: r for r in _ptrack(client, auth, p["id"])}
    for task in ("a1", "a2"):
        client.patch(f"/api/records/ptrack/{rows[task]['id']}", json={"checked": True}, headers=auth)

    res = client.post(
        f"/api/projects/{p['id']}/template", json={"templateNo": 2}, headers=auth
    )
    assert res.status_code == 200, res.get_json()
    body = res.get_json()
    assert body["templateNo"] == 2
    new_rows = {r["task"]: r for r in _ptrack(client, auth, p["id"])}
    assert sorted(new_rows) == ["a1", "x1"]
    assert new_rows["a1"]["checked"] is True   # same text -> carried over
    assert new_rows["x1"]["checked"] is False
    assert new_rows["x1"]["process"] == "X" and new_rows["x1"]["dayRange"] == 10
    assert (body["processCount"], body["processDone"]) == (2, 1)
    assert any("Changed process template" in a["detail"] for a in body["activities"])


def test_change_template_validation_and_authz(client, auth):
    _two_templates()
    p = _project(client, auth)
    url = f"/api/projects/{p['id']}/template"
    assert client.post(url, json={"templateNo": 9}, headers=auth).status_code == 422
    assert client.post(url, json={}, headers=auth).status_code == 422
    # same template -> no-op, checklist untouched
    before = [r["id"] for r in _ptrack(client, auth, p["id"])]
    assert client.post(url, json={"templateNo": 1}, headers=auth).status_code == 200
    assert [r["id"] for r in _ptrack(client, auth, p["id"])] == before
    member = _register(client, "m@x.com")
    assert client.post(url, json={"templateNo": 2}, headers=member).status_code == 403
    assert client.post("/api/projects/999/template", json={"templateNo": 2}, headers=auth).status_code == 404
